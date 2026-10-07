"""Minimal Devin API client (stdlib only).

Uses DEVIN_API_KEY. Every function supports dry_run=True so swarms can be
planned and demoed without credentials.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

API_BASE = os.environ.get("DEVIN_API_BASE", "https://api.devin.ai/v3")


class DevinAPIError(RuntimeError):
    pass


@dataclass(frozen=True)
class SessionInfo:
    session_id: str
    url: str
    status: str = "unknown"
    pull_requests: tuple[str, ...] = ()


def _request(method: str, path: str, api_key: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500]
        raise DevinAPIError(f"{method} {path} -> {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise DevinAPIError(f"{method} {path} failed: {e.reason}") from e


def get_key(explicit: str | None = None) -> str:
    key = explicit or os.environ.get("DEVIN_API_KEY")
    if not key:
        raise DevinAPIError(
            "no API key: set DEVIN_API_KEY or pass --api-key "
            "(use --dry-run to plan without one)"
        )
    return key


def create_session(
    prompt: str,
    api_key: str,
    repos: list[str] | None = None,
    tags: list[str] | None = None,
    title: str | None = None,
    dry_run: bool = False,
) -> SessionInfo:
    """POST /v3/sessions — start a Devin session."""
    if dry_run:
        return SessionInfo(
            session_id="dry-run",
            url="https://app.devin.ai/sessions/dry-run",
            status="dry-run",
        )
    body: dict = {"prompt": prompt}
    if repos:
        body["repos"] = repos
    if tags:
        body["tags"] = tags
    if title:
        body["title"] = title
    resp = _request("POST", "/sessions", api_key, body)
    sid = resp.get("session_id") or resp.get("devin_id") or resp.get("id", "")
    url = resp.get("url") or f"https://app.devin.ai/sessions/{sid.replace('devin-', '')}"
    return SessionInfo(session_id=sid, url=url, status=str(resp.get("status", "created")))


def get_session(session_id: str, api_key: str) -> SessionInfo:
    """GET /v3/sessions/{id} — status + PRs of a running session."""
    sid = session_id if session_id.startswith("devin-") else f"devin-{session_id}"
    resp = _request("GET", f"/sessions/{sid}", api_key)
    prs = resp.get("pull_requests") or []
    urls = tuple(
        pr if isinstance(pr, str) else pr.get("pr_url", "") for pr in prs
    )
    return SessionInfo(
        session_id=sid,
        url=resp.get("url", ""),
        status=str(resp.get("status_enum", resp.get("status", "unknown"))).lower(),
        pull_requests=urls,
    )


def is_done(status: str) -> bool:
    """Session statuses that mean the session stopped moving."""
    return status in {
        "finished", "stopped", "suspend", "suspended",
        "blocked", "sleeping", "exited",
    }
