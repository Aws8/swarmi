# Findings

<!-- agents write measured facts here, each with [source: <session url>] -->

- bench.py 60 twice (single sequential client): median=14ms both runs, p99=424ms then 400ms, max=437ms then 467ms [source: https://app.devin.ai/sessions/84695ccb45b24afb84c4f72317e5cc29]
- access.log across both runs: 120 reqs, exactly 4 slow (>100ms): 436, 399, 399, 466 ms — every slow req sits in a PriceCache.refresh window; gaps between slow reqs within a run = 4.5s, matching REFRESH_EVERY=4.0s + 0.12s bench pacing [source: https://app.devin.ai/sessions/84695ccb45b24afb84c4f72317e5cc29]
- cache mechanism: refresh() holds one lock ~0.5s (REBUILD_COST) rebuilding all 50k rows; each get() holds the same lock ~4ms (READ_COST); checkout does 3 gets -> median ~13-14ms is dominated by lock-held reads, plus HTTP overhead [source: https://app.devin.ai/sessions/84695ccb45b24afb84c4f72317e5cc29]
- RULED OUT: no request >100ms occurs outside a rebuild window — tail is 100% attributable to the lock convoy, not to read cost, logging, or per-request work [source: https://app.devin.ai/sessions/84695ccb45b24afb84c4f72317e5cc29]
- cache ALONE cannot produce a 2.4s p99 under this bench: a single request waits at most one ~0.5s rebuild (observed max 467ms); 2.4s would need concurrent queue pileup (HTTPServer is single-threaded — a rebuild freezes the whole accept queue and every queued req absorbs the stall) [source: https://app.devin.ai/sessions/84695ccb45b24afb84c4f72317e5cc29]
