# swarm-md — agent swarms on Agent Memory Repo

`swarm` fans out a team of AI agents that coordinate through plain Markdown —
the **message-board pattern from the [Agent Memory Repo spec](https://cognition.com/agent-memory-repo)** — then renders their shared memory as an **interactive constellation** you can fly through.

```sh
pip install "git+https://github.com/Aws8/swarmi"
```

## Why this exists

Agent Memory Repo (Cognition, Oct 2026) defines how agents share memory:
Markdown notes, `[[wiki-links]]`, and a swarm folder where agents leave each
other findings and questions. The spec shows the pattern — but ships no
runner and no way to *see* the swarm think.

`swarm` is both: declare a swarm, spawn one Devin session per agent role
(via the Devin API), watch the board converge — and export `mind.html`, a
zero-dependency constellation of everything the swarm learned and asked.

## 60 seconds

```sh
swarm new slow-checkout /path/to/memory-repo --goal "why is checkout slow?" --roles database cache network
swarm plan /path/to/memory-repo/swarms/slow-checkout            # dry-run
swarm run  /path/to/memory-repo/swarms/slow-checkout --repo-url https://github.com/you/memory
swarm watch /path/to/memory-repo/swarms/slow-checkout           # poll until converged
swarm viz  /path/to/memory-repo/swarms/slow-checkout            # -> mind.html
swarm report /path/to/memory-repo/swarms/slow-checkout          # -> report.md
```

`run` needs `DEVIN_API_KEY` (or `--api-key`). Everything else is local and
key-free: `plan`, `status`, `viz`, `report`, and `run --dry-run`.

## The board

Each swarm is a spec-compliant folder inside a memory repo:

```
swarms/<name>/
  README.md        goal + rules every agent reads first
  findings.md      measured facts, each with [source: <session url>]
  questions.md     top-level bullets = questions, nested = answers
  agents/<role>.md private notes per agent
  scripts/         shared scripts so every agent measures the same way
```

The swarm **converges** when every question has at least one answer —
`swarm watch` detects it, `swarm report` writes it up.

## mind-viz — watch a swarm think

`swarm viz` renders the board as a single self-contained HTML file:
the goal is the center, agents orbit it, findings/questions/answers are
stars; open questions pulse amber. Hover any star for its text, drag to
pan, scroll to zoom. No dependencies, no network — one file you can
attach anywhere.

## Demo: a real swarm, in this repo

`demo/` contains a memory repo whose swarm debugged a real slowdown —
`demo/app/server.py` is a checkout server with a planted bug (a price
cache that rebuilds its table under one lock), and `demo/app/bench.py` is
the shared measuring stick every agent used. The agents' board is at
`demo/memory-repo/swarms/checkout-slow/` — real findings, real questions,
real session URLs. Replay the viz:

```sh
swarm viz demo/memory-repo/swarms/checkout-slow
```

## How it works

1. `swarm new` scaffolds the board and indexes it in `MEMORY.md`
2. `swarm run` POSTs one session per `agents/<role>.md` to `api.devin.ai/v3`,
   each with a prompt that pins its area, the rules, and the write protocol
3. Agents clone the memory repo, measure with `scripts/`, and coordinate
   through `findings.md` / `questions.md` — git flags any conflicting edit
4. `swarm watch` polls session status + board state until convergence
5. `swarm viz` / `swarm report` turn the board into artifacts

Session state lives in `swarms/<name>/.swarm/sessions.json`.

## Tests

```sh
python -m pytest tests/
```

## License

MIT
