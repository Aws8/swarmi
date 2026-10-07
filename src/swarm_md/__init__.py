"""swarm-md: run agent swarms on Agent Memory Repo message boards.

Declare a swarm folder in a memory repo (the pattern from
https://cognition.com/agent-memory-repo), then fan out one Devin session
per agent file. Agents coordinate by writing findings and questions to
shared Markdown files; git flags conflicting edits.

    swarm new swarms/slow-checkout --goal "why is checkout slow?"
    swarm plan swarms/slow-checkout           # dry-run, no API key needed
    swarm run swarms/slow-checkout            # spawns Devin sessions
    swarm status swarms/slow-checkout         # board + session state
    swarm watch swarms/slow-checkout          # poll until convergence
    swarm report swarms/slow-checkout         # final report.md
"""

__version__ = "0.1.0"
