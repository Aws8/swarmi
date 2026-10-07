# Agent: database

- Area: database
- Notes go here as the agent works [added: 2026-10-07]

## Verdict: data access does NOT explain the tail

There is no real database: `CACHE.get()` is a dict lookup on a 50k-entry
in-memory table with a simulated 4ms row fetch, 3 per request, each under ONE
shared `threading.Lock` (demo/app/server.py:49-52,63).

Measured (all via `swarms/checkout-slow/scripts/bench.py 60`):

| run | median | p99 | max |
|---|---|---|---|
| baseline | 15ms | 449ms | 1560ms |
| READ_COST=0 | 1ms | 449-457ms | 492ms |
| REBUILD_COST=0.005 | 15ms | 17ms | 38ms |

- Data access is ~all of the median (14ms of 15ms) but bounded — removing it
  entirely leaves the ~450ms tail. The tail is WAIT time on the shared lock
  during the 500ms rebuild that fires every 4s, i.e. a cache/lock-convoy
  problem, not a data-access problem.
- access.log: slow requests (>100ms) occur ~4.5s apart, matching the rebuild
  cadence. Client-side max (1560ms) exceeds server-logged handler max (448ms)
  — accept-queue backlog behind the single-threaded server adds more tail.
- Ruled out: row count, query cost, index misses, I/O, pooling, N+1.

[added: 2026-10-07]
