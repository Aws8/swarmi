"""Parse a swarm folder — the message-board pattern from the
Agent Memory Repo spec:

    swarms/<name>/
      README.md        goal + rules (every agent reads this first)
      findings.md      what each agent has measured
      questions.md     agents ask and answer each other
      agents/<role>.md one notes file per agent
      scripts/         shared scripts (e.g. the one benchmark)

Protocol: top-level bullets in questions.md are questions; a nested
bullet under a question is an answer. The swarm is *converged* when
every question has at least one answer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

BULLET_RE = re.compile(r"^(?P<indent>[ \t]*)(?:[-*+]|\d+[.)])\s+(?P<body>.*)$")
HEADING_RE = re.compile(r"^#{1,6}\s+(?:swarm\s*:\s*)?(.+?)\s*$", re.MULTILINE | re.IGNORECASE)

REQUIRED_FILES = ["README.md", "findings.md", "questions.md"]


@dataclass(frozen=True)
class Question:
    asker: str  # parsed from "Name asks: ..." or filename fallback
    text: str
    line: int
    answers: tuple[str, ...] = ()

    @property
    def answered(self) -> bool:
        return bool(self.answers)


@dataclass
class Board:
    """Parsed state of one swarm folder."""

    path: Path
    name: str
    goal: str
    findings: list[str]
    questions: list[Question]
    agents: list[str]  # role names from agents/*.md
    scripts: list[str]

    @property
    def open_questions(self) -> list[Question]:
        return [q for q in self.questions if not q.answered]

    @property
    def converged(self) -> bool:
        return bool(self.questions) and not self.open_questions

    @property
    def missing_files(self) -> list[str]:
        return [f for f in REQUIRED_FILES if not (self.path / f).exists()]


def _bullets(text: str) -> list[tuple[int, int, str]]:
    """(indent, line_no, body) for each bullet line, fences skipped."""
    out = []
    in_fence = False
    for i, line in enumerate(text.splitlines(), start=1):
        if re.match(r"^\s*(```+|~~~+)", line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = BULLET_RE.match(line)
        if m:
            out.append((len(m.group("indent").expandtabs(4)), i, m.group("body").strip()))
    return out


def _strip_meta(body: str) -> str:
    return re.sub(r"\s*\[[^\]]+\]\s*$", "", body).strip()


def parse_questions(path: Path) -> list[Question]:
    if not path.exists():
        return []
    bullets = _bullets(path.read_text(encoding="utf-8"))
    rows: list[tuple[str, str, int, list[str]]] = []
    for indent, lineno, body in bullets:
        if indent == 0:
            asker = "unknown"
            m = re.match(r"^(?P<who>.+?)\s+asks\s*:\s*(?P<q>.*)$", body, re.IGNORECASE)
            text = _strip_meta(body)
            if m:
                asker = m.group("who").strip()
                text = _strip_meta(m.group("q"))
            rows.append((asker, text, lineno, []))
        elif rows:
            rows[-1][3].append(_strip_meta(body))
    return [Question(asker=a, text=t, line=l, answers=tuple(ans)) for a, t, l, ans in rows]


def parse_findings(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [_strip_meta(body) for indent, _, body in _bullets(path.read_text(encoding="utf-8")) if indent == 0]


def parse_goal(path: Path) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    heading = HEADING_RE.search(text)
    if heading:
        return heading.group(1).strip()
    bullets = _bullets(text)
    return _strip_meta(bullets[0][2]) if bullets else path.parent.name


def load(swarm_dir: Path) -> Board:
    swarm_dir = swarm_dir.resolve()
    if not swarm_dir.is_dir():
        raise NotADirectoryError(f"not a swarm folder: {swarm_dir}")
    agents_dir = swarm_dir / "agents"
    scripts_dir = swarm_dir / "scripts"
    return Board(
        path=swarm_dir,
        name=swarm_dir.name,
        goal=parse_goal(swarm_dir / "README.md"),
        findings=parse_findings(swarm_dir / "findings.md"),
        questions=parse_questions(swarm_dir / "questions.md"),
        agents=sorted(p.stem for p in agents_dir.glob("*.md")) if agents_dir.is_dir() else [],
        scripts=sorted(p.name for p in scripts_dir.glob("*")) if scripts_dir.is_dir() else [],
    )


def status_lines(board: Board, sessions: list[tuple[str, str]] | None = None) -> list[str]:
    """Human-readable status for `swarm status`/`watch` ticks."""
    lines = [f"swarm: {board.name}", f"goal:  {board.goal or '(none parsed)'}"]
    if board.missing_files:
        lines.append(f"MISSING: {', '.join(board.missing_files)} — run `swarm new` or fix the folder")
    lines.append(f"agents: {len(board.agents)} ({', '.join(board.agents) or 'none'})")
    lines.append(f"findings: {len(board.findings)}")
    lines.append(f"questions: {len(board.questions)} ({len(board.open_questions)} open)")
    for q in board.open_questions:
        lines.append(f"  open: {q.asker} asks: {q.text} (questions.md:{q.line})")
    if sessions:
        lines.append("sessions:")
        for role, state in sessions:
            lines.append(f"  {role}: {state}")
    lines.append("converged" if board.converged else "not converged")
    return lines


def render_report(board: Board, sessions: list[tuple[str, str]] | None = None) -> str:
    """Markdown report of a finished (or in-flight) swarm."""
    lines = [
        f"# Swarm report: {board.name}",
        "",
        f"**Goal:** {board.goal}",
        "",
        f"**Result:** {'converged' if board.converged else 'incomplete'} — "
        f"{len(board.findings)} finding(s), {len(board.questions)} question(s), "
        f"{len(board.open_questions)} open",
        "",
        "## Findings",
    ]
    lines += [f"- {f}" for f in board.findings] or ["- (none yet)"]
    lines += ["", "## Questions & answers"]
    if not board.questions:
        lines.append("- (none)")
    for q in board.questions:
        lines.append(f"- **{q.asker}** asked: {q.text}")
        for a in q.answers:
            lines.append(f"  - {a}")
    if sessions:
        lines += ["", "## Sessions"]
        for role, state in sessions:
            lines.append(f"- {role}: {state}")
    lines += ["", f"_Generated by swarm-md for {board.path}_"]
    return "\n".join(lines)
