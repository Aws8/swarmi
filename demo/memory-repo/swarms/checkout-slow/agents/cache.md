# Agent: cache

- Area: cache
- Notes go here as the agent works [added: 2026-10-07]

## Verdict

**Yes — the cache lock convoy is the measured cause of the tail in this demo.** Every request >100ms (4 of 120 across two bench.py 60 runs) lands inside a `PriceCache.refresh()` window; slow-request spacing = 4.5s, matching `REFRESH_EVERY=4.0s`. Nothing else in the request path produces >100ms.

## Measurements

- bench.py 60 run 1: median=14ms p99=424ms max=437ms
- bench.py 60 run 2: median=14ms p99=400ms max=467ms
- access.log: 120 reqs, 4 slow — 436/399/399/466 ms; intra-run gaps 4.5s (4s refresh + 0.12s pacing)

## Mechanism

- `refresh()` rebuilds the full 50k-row table under ONE lock, holding it ~0.5s every 4s (server.py:38-47)
- `get()` takes the same lock for ~4ms simulated read (server.py:49-52); checkout = 3 gets -> ~12-14ms median
- Request arriving during rebuild queues behind the write lock -> waits remaining rebuild time (~0.4-0.5s)
- Amplifier under concurrency: `HTTPServer` is single-threaded, so the rebuild freezes the whole accept queue; every queued request absorbs the stall — that's how a 0.5s stall could grow toward multi-second tail under load

## Ruled out

- Read cost / per-request work / access.log writes: all fast reqs are ~13-14ms, none drift upward over the run
- Cache alone producing 2.4s: impossible for one request under the sequential bench — bounded by REBUILD_COST=0.5s. Multi-second tail needs concurrent queue pileup (see questions.md)

## Fix direction (not applied — outside scope)

Build the new table outside the lock and swap the reference (copy-on-write), or use a read-write lock so reads don't queue behind rebuilds.
