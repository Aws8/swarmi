"""Swarm lifecycle: scaffold folders, build agent prompts, spawn sessions."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .board import load

STATE_DIR = ".swarm"
STATE_FILE = "sessions.json"

README_TEMPLATE = """# Swarm: {goal}

- The goal: {goal} [added: {today}]
- Measure only with the scripts in [[{rel_scripts}]], so numbers compare
- Before each step, pull and read findings and questions
- Write what you measure in [[{rel_findings}]], including what you rule out
- If another agent's area might explain what you see, ask in [[{rel_questions}]]
- Commit and push after every edit — the board is the single source of truth
"""

FINDINGS_TEMPLATE = """# Findings

<!-- agents write measured facts here, each with [source: <session url>] -->
"""

QUESTIONS_TEMPLATE = """# Questions

<!-- top-level bullets are questions: "- <area> asks: ..." — nested bullets are answers -->
"""

AGENT_TEMPLATE = """# Agent: {role}

- Area: {role}
- Notes go here as the agent works [added: {today}]
"""


@dataclass(frozen=True)
class SpawnResult:
    role: str
    session_id: str
    url: str
    status: str


def new_swarm(
    memory_repo: Path,
    name: str,
    goal: str,
    roles: list[str],
    git_commit: bool = True,
) -> list[str]:
    """Scaffold a spec-compliant swarm folder inside a memory repo."""
    root = Path(memory_repo).resolve()
    swarm_dir = root / "swarms" / name
    if swarm_dir.exists():
        raise FileExistsError(f"swarm already exists: {swarm_dir}")
    (swarm_dir / "agents").mkdir(parents=True)
    (swarm_dir / "scripts").mkdir()

    today = date.today().isoformat()
    actions: list[str] = []

    def w(rel: str, text: str) -> None:
        p = swarm_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        actions.append(f"created swarms/{name}/{rel}")

    w("README.md", README_TEMPLATE.format(
        goal=goal,
        today=today,
        rel_scripts=f"swarms/{name}/scripts",
        rel_findings=f"swarms/{name}/findings.md",
        rel_questions=f"swarms/{name}/questions.md",
    ))
    w("findings.md", FINDINGS_TEMPLATE)
    w("questions.md", QUESTIONS_TEMPLATE)
    for role in roles:
        w(f"agents/{role}.md", AGENT_TEMPLATE.format(role=role, today=today))
    w("scripts/README.md",
      "# Shared scripts\n\nEvery agent measures with the same scripts so numbers compare.\n")

    # index the swarm in MEMORY.md
    memory_md = root / "MEMORY.md"
    if memory_md.exists():
        text = memory_md.read_text(encoding="utf-8")
        link = f"[[swarms/{name}/README]]"
        if link not in text:
            lines = text.splitlines()
            idx = next(
                (i for i, l in enumerate(lines) if l.strip().lower().startswith("#") and "index" in l.lower()),
                None,
            )
            if idx is None:
                lines += ["", "## Index"]
                idx = len(lines) - 1
            insert_at = len(lines)
            for j in range(idx + 1, len(lines)):
                if lines[j].lstrip().startswith("#"):
                    insert_at = j
                    break
            lines.insert(insert_at, f"- {link}")
            memory_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
            actions.append(f"indexed {link} in MEMORY.md")

    if git_commit and (root / ".git").exists():
        subprocess.run(["git", "add", f"swarms/{name}", "MEMORY.md"], cwd=root, capture_output=True, timeout=30)
        subprocess.run(
            ["git", "-c", "user.email=swarm-md@local", "-c", "user.name=swarm-md",
             "commit", "-m", f"swarm: {name} — {goal[:60]}"],
            cwd=root, capture_output=True, timeout=30,
        )
        actions.append("committed swarm scaffold")
    return actions


def agent_prompt(
    swarm_dir: Path,
    role: str,
    memory_repo_url: str,
    branch: str = "main",
) -> str:
    """The prompt each spawned Devin session receives."""
    swarm_dir = Path(swarm_dir)
    rel = swarm_dir.name
    agent_file = swarm_dir / "agents" / f"{role}.md"
    notes = agent_file.read_text(encoding="utf-8") if agent_file.exists() else ""
    board = load(swarm_dir)
    return f"""You are the **{role}** agent in a swarm debugging: {board.goal}

Setup:
1. Clone the memory repo {memory_repo_url} (branch {branch}) — it contains this swarm's message board.
2. Read swarms/{rel}/README.md for the goal and rules, then swarms/{rel}/findings.md and swarms/{rel}/questions.md.
3. Your notes file is swarms/{rel}/agents/{role}.md — your current notes:
{notes.strip() or '(empty)'}

Rules:
- Work ONLY your area ({role}). Rule out or measure, don't speculate.
- Measure with the shared scripts in swarms/{rel}/scripts/ so numbers compare.
- Write every fact you learn into swarms/{rel}/findings.md as one-line bullets, each ending [source: <this session's url>]. Include what you RULE OUT.
- If another agent's area might explain what you see, add a top-level bullet to swarms/{rel}/questions.md: "- {role} asks: <question> [source: <url>]". Answer other agents' questions as a nested bullet.
- Commit and push after EVERY edit — other agents are pulling the board constantly.
- Never edit another agent's notes file. Shared files are findings.md and questions.md only.
- Stop when you have found and written the cause for your area, or proven it is not yours."""


def state_path(swarm_dir: Path) -> Path:
    return Path(swarm_dir) / STATE_DIR / STATE_FILE


def load_state(swarm_dir: Path) -> dict[str, dict]:
    p = state_path(swarm_dir)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_state(swarm_dir: Path, state: dict[str, dict]) -> None:
    p = state_path(swarm_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2), encoding="utf-8")
