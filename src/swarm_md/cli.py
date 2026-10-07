"""swarm — run agent swarms on Agent Memory Repo message boards."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from . import __version__
from .api import DevinAPIError, create_session, get_key, get_session, is_done
from .board import load, render_report, status_lines
from .swarm import agent_prompt, load_state, new_swarm, save_state
from .viz import render_viz

DEFAULT_ROLES = ["database", "cache", "network"]


def _swarm_dir(arg: str) -> Path:
    p = Path(arg)
    if not p.is_dir():
        # allow `swarm <cmd> memory-repo --name x` style: treat arg as repo root
        raise SystemExit(f"no swarm folder at {p} — create one with `swarm new`")
    return p


def _repo_root(swarm_dir: Path) -> Path:
    # swarms/<name> lives two levels under the memory repo root
    return swarm_dir.resolve().parents[1] if swarm_dir.parent.name == "swarms" else swarm_dir.resolve()


def cmd_new(args: argparse.Namespace) -> int:
    roles = args.roles or DEFAULT_ROLES
    actions = new_swarm(Path(args.repo), args.name, args.goal, roles)
    for a in actions:
        print(a)
    print(f"\nswarm ready: {Path(args.repo) / 'swarms' / args.name}")
    print("next: swarm plan " + str(Path(args.repo) / "swarms" / args.name))
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    swarm_dir = _swarm_dir(args.swarm)
    board = load(swarm_dir)
    print(f"goal: {board.goal}")
    print(f"would spawn {len(board.agents)} session(s):")
    for role in board.agents:
        print(f"  - {role}")
    if args.prompts:
        print("\n--- prompts ---")
        for role in board.agents:
            print(f"\n### {role}\n{agent_prompt(swarm_dir, role, args.repo_url or '<memory repo url>', args.branch)}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    swarm_dir = _swarm_dir(args.swarm)
    board = load(swarm_dir)
    if board.missing_files:
        print(f"incomplete swarm folder, missing: {', '.join(board.missing_files)}")
        return 1
    state = load_state(swarm_dir)
    roles = args.roles or board.agents
    spawned = 0
    for role in roles:
        if role in state and state[role].get("session_id"):
            print(f"  {role}: already spawned ({state[role]['session_id']}) — skipping")
            continue
        prompt = agent_prompt(swarm_dir, role, args.repo_url, args.branch)
        try:
            info = create_session(
                prompt,
                api_key=get_key(args.api_key) if not args.dry_run else "",
                repos=args.repos,
                tags=["swarm", board.name, role],
                title=f"swarm:{board.name}/{role}",
                dry_run=args.dry_run,
            )
        except DevinAPIError as e:
            print(f"  {role}: FAILED — {e}")
            continue
        state[role] = {
            "session_id": info.session_id,
            "url": info.url,
            "status": info.status,
        }
        spawned += 1
        print(f"  {role}: {info.url}")
    save_state(swarm_dir, state)
    print(f"\n{spawned} session(s) spawned; board: {swarm_dir}")
    print("next: swarm watch " + str(swarm_dir))
    return 0


def _refresh_statuses(swarm_dir: Path, api_key: str | None) -> list[tuple[str, str]]:
    state = load_state(swarm_dir)
    out = []
    for role, s in state.items():
        sid = s.get("session_id", "")
        if args_key_ok(sid, api_key):
            try:
                info = get_session(sid, api_key)
                s["status"] = info.status
            except DevinAPIError:
                pass
        out.append((role, f"{s.get('status', '?')} — {s.get('url', sid)}"))
    save_state(swarm_dir, state)
    return out


def args_key_ok(sid: str, api_key: str | None) -> bool:
    return bool(api_key) and sid not in ("", "dry-run")


def cmd_status(args: argparse.Namespace) -> int:
    swarm_dir = _swarm_dir(args.swarm)
    board = load(swarm_dir)
    sessions = _refresh_statuses(swarm_dir, args.api_key)
    print("\n".join(status_lines(board, sessions)))
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    swarm_dir = _swarm_dir(args.swarm)
    deadline = time.time() + args.timeout * 60
    while True:
        board = load(swarm_dir)
        sessions = _refresh_statuses(swarm_dir, args.api_key)
        stamp = time.strftime("%H:%M:%S")
        print(f"--- {stamp} ---")
        print("\n".join(status_lines(board, sessions)))
        all_done = all(is_done(s.get("status", "")) for s in load_state(swarm_dir).values()) if load_state(swarm_dir) else False
        if board.converged:
            print("\nswarm converged — run: swarm report " + str(swarm_dir))
            return 0
        if all_done and board.open_questions:
            print("\nall sessions done but questions remain open — agents may need a nudge")
            return 1
        if time.time() > deadline:
            print(f"\ntimeout after {args.timeout}m — swarm still running")
            return 2
        time.sleep(args.interval)


def cmd_report(args: argparse.Namespace) -> int:
    swarm_dir = _swarm_dir(args.swarm)
    board = load(swarm_dir)
    sessions = _refresh_statuses(swarm_dir, args.api_key)
    text = render_report(board, sessions)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        out = swarm_dir / "report.md"
        out.write_text(text, encoding="utf-8")
        print(f"wrote {out}")
    return 0


def cmd_viz(args: argparse.Namespace) -> int:
    swarm_dir = _swarm_dir(args.swarm)
    board = load(swarm_dir)
    out = Path(args.out) if args.out else swarm_dir / "mind.html"
    out.write_text(render_viz(board), encoding="utf-8")
    print(f"wrote {out} — open it in a browser")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="swarm",
        description="Run agent swarms on Agent Memory Repo message boards.",
    )
    p.add_argument("--version", action="version", version=f"swarm-md {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("new", help="scaffold a swarm folder inside a memory repo")
    n.add_argument("name", help="swarm slug, e.g. slow-checkout")
    n.add_argument("repo", help="path to the memory repo (contains MEMORY.md)")
    n.add_argument("--goal", required=True, help="what the swarm is investigating")
    n.add_argument("--roles", nargs="+", help="agent role names (default: database cache network)")
    n.set_defaults(fn=cmd_new)

    pl = sub.add_parser("plan", help="dry-run: show what run would spawn")
    pl.add_argument("swarm", help="path to swarms/<name>")
    pl.add_argument("--repo-url", help="git URL agents will clone (for prompt preview)")
    pl.add_argument("--branch", default="main")
    pl.add_argument("--prompts", action="store_true", help="print full agent prompts")
    pl.set_defaults(fn=cmd_plan)

    r = sub.add_parser("run", help="spawn one Devin session per agent")
    r.add_argument("swarm")
    r.add_argument("--repo-url", required=True, help="git URL agents will clone")
    r.add_argument("--branch", default="main")
    r.add_argument("--repos", nargs="*", help="repo allowlist for spawned sessions")
    r.add_argument("--roles", nargs="*", help="subset of roles to spawn")
    r.add_argument("--api-key", help="Devin API key (or DEVIN_API_KEY)")
    r.add_argument("--dry-run", action="store_true", help="record fake sessions, no API calls")
    r.set_defaults(fn=cmd_run)

    s = sub.add_parser("status", help="board state + session statuses, once")
    s.add_argument("swarm")
    s.add_argument("--api-key")
    s.set_defaults(fn=cmd_status)

    w = sub.add_parser("watch", help="poll until the swarm converges")
    w.add_argument("swarm")
    w.add_argument("--api-key")
    w.add_argument("--interval", type=int, default=30, help="seconds between polls")
    w.add_argument("--timeout", type=int, default=120, help="minutes before giving up")
    w.set_defaults(fn=cmd_watch)

    rp = sub.add_parser("report", help="write report.md for the swarm")
    rp.add_argument("swarm")
    rp.add_argument("--api-key")
    rp.add_argument("--out", help="output path (default: <swarm>/report.md)")
    rp.set_defaults(fn=cmd_report)

    v = sub.add_parser("viz", help="render the swarm's memory as an interactive constellation")
    v.add_argument("swarm")
    v.add_argument("--out", help="output html (default: <swarm>/mind.html)")
    v.set_defaults(fn=cmd_viz)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
