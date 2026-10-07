# Swarm report: checkout-slow

**Goal:** Why is the demo checkout endpoint slow? p99 is ~2.4s but median ~80ms. Find the cause.

**Result:** converged — 21 finding(s), 3 question(s), 0 open

## Findings
- bench.py 60 twice (single sequential client): median=14ms both runs, p99=424ms then 400ms, max=437ms then 467ms
- access.log across both runs: 120 reqs, exactly 4 slow (>100ms): 436, 399, 399, 466 ms — every slow req sits in a PriceCache.refresh window; gaps between slow reqs within a run = 4.5s, matching REFRESH_EVERY=4.0s + 0.12s bench pacing
- cache mechanism: refresh() holds one lock ~0.5s (REBUILD_COST) rebuilding all 50k rows; each get() holds the same lock ~4ms (READ_COST); checkout does 3 gets -> median ~13-14ms is dominated by lock-held reads, plus HTTP overhead
- RULED OUT: no request >100ms occurs outside a rebuild window — tail is 100% attributable to the lock convoy, not to read cost, logging, or per-request work
- cache ALONE cannot produce a 2.4s p99 under this bench: a single request waits at most one ~0.5s rebuild (observed max 467ms); 2.4s would need concurrent queue pileup (HTTPServer is single-threaded — a rebuild freezes the whole accept queue and every queued req absorbs the stall)
- bench.py 60 solo client (this VM): median=14ms p99=450ms max=470ms — reproduces the tail shape at ~0.45s, not 2.4s
- raw TCP connect only, 295 samples over 12s spanning 3 rebuilds: median=0.2ms p99=0.5ms max=2.1ms — connect setup is never the bottleneck at solo load
- GET / (handler touches NO cache lock), 200 samples over ~8s spanning 2 rebuilds: median=0.9ms p99=1.5ms max=11.9ms — HTTP stack+transport stay fast during rebuilds; the stall is inside the checkout handler
- /checkout split timings (60 reqs): connect phase p99=0.3ms vs response phase p99=445.8ms — 100% of the solo tail is post-connect server think time
- server access.log vs client-side over 121 reqs: median 14.0 vs 14.4ms, p99 449 vs 446ms, max 469 vs 469.6ms — client≈server, transport adds ~0ms at median and tail
- wire facts: HTTP/1.0, Server: BaseHTTP/0.6, Content-Length 16, connection closed per request — RULED OUT: payload size, header overhead, missing keep-alive (fresh connect costs ~0.2ms)
- concurrency probe C=4: p99=505ms (vs solo ~450ms) — tail grows slowly with queue depth
- concurrency probe C=16: connect p99=2017ms max=2020ms, response p99=580ms, total p99=2090ms ≈ reported ~2.4s — during the ~0.5s handler stall the single-threaded accept loop stops, listen backlog (request_queue_size=5) overflows, client SYNs are dropped and retransmitted after ~2s
- VERDICT: transport is an amplifier, not the cause — solo connect is sub-ms and solo tail is all server think time; the multi-second tail only appears when concurrent connects overflow the backlog during a stall
- Baseline, unmodified server, `bench.py 60`: median=15ms p99=449ms max=1560ms
- Per-request data access = exactly 3 `CACHE.get()` dict lookups on a 50k-entry in-memory table, each a simulated 4ms row fetch under ONE shared threading.Lock (demo/app/server.py:49-52,63). There is no real database, no queries, scans, or aggregations.
- Variant server with data-fetch cost removed (READ_COST=0, rebuild unchanged): median=1ms → data access is ~14ms, i.e. ~all of the typical request, but p99 stayed 449-457ms across 2 runs → the tail is NOT data-access work, it is wait time.
- Variant server with rebuild lock-hold shrunk (REBUILD_COST=0.005, READ_COST=4ms unchanged): p99=17ms max=38ms → tail is driven by the ~500ms lock-hold every 4s that price reads queue behind.
- Server-side access.log from baseline run: only 2 of 60 requests >100ms (448ms, 395ms), spaced 4.5s apart — matching the 4s rebuild cadence; slow requests are exactly the ones straddling a rebuild.
- Bench client max (1560ms) exceeded the server-logged max handler time (448ms): the extra ~1.1s is accept-queue backlog behind the single-threaded HTTPServer while it was stuck in a blocked request — part of the client-visible tail is serialization, not handler work.
- RULED OUT (database area): table size, query cost, missing index, I/O, connection pooling, N+1 — no DB exists; per-request data work is bounded at ~12-14ms and cannot produce a 400ms+ tail.

## Questions & answers
- **cache** asked: the shared bench (sequential) gives p99 ~420ms, fully explained by the 0.5s rebuild stall. Was the reported p99 ~2.4s / median ~80ms measured under concurrent clients (queue pileup through the single-threaded server amplifying the stall), or is it the production framing this demo approximates? If concurrent load is in scope, network — can you measure the queue-depth effect?
  - network answers: measured. C=1 p99≈450ms (all response phase), C=4 p99≈505ms, C=16 connect p99≈2017ms while response p99≈580ms → total ≈2.1s. The queue-depth effect is real and it is a cliff, not linear: during a ~0.5s stall the accept loop stops, the 5-deep listen backlog overflows, SYNs drop, and clients retransmit after ~2s. So the reported p99 ~2.4s (and median ~80ms vs our 14ms) only fits a concurrent-load reference env; solo sequential caps at ~0.5s.
  - database adds: even with the SEQUENTIAL bench client I measured client max=1560ms vs server-logged handler max=448ms — a request queued in the accept backlog behind a rebuild-blocked one roughly doubles its wait. Concurrency would multiply that: supports the queue-pileup amplification theory for 2.4s.
- **database** asked: reads share ONE lock with the 4s rebuild (server.py:41 vs :50). Can the cache rebuild off-lock (build a new table, then swap) so reads never queue? With rebuild hold=5ms the tail collapses to p99=17ms.
  - cache answers: yes, correct — this lock structure is already copy-on-write compatible. get() only READS self._table under the lock and refresh() already rebinds rather than mutates, so building dict(PRICES) off-lock then swapping `self._table = new` inside the lock is safe: each get() sees either the old or new fully-built dict, never a partial one. Keep the swap itself under the lock so it stays ordered with the locked readers. Single refresher thread, so no builder-vs-builder race; and since PRICES is static, a stale snapshot can't overwrite newer data — only caveat worth noting if the source ever becomes dynamic (then builds would need a sequence/version guard). Your 5ms-hold result matches the predicted bound: reads stop paying the ~0.5s build and only serialize on the ~us swap. Bonus cross-area effect: removing the stall also removes network's amplifier — no frozen accept queue, no SYN drops.
- **database** asked: client max (1560ms) > server-logged handler max (448ms) — is the accept-queue backlog behind the single-threaded HTTPServer in the network/concurrency area? Worth checking whether request queuing amplifies the tail beyond lock wait alone.
  - network answers (already measured above): yes — queuing is the amplifier; C=16 shows SYN drops + ~2s retransmit once the 5-deep backlog overflows during a stall.

## Sessions
- database: running — https://app.devin.ai/sessions/49606b3877994cbc9a1d7162cd86a3ba
- cache: running — https://app.devin.ai/sessions/84695ccb45b24afb84c4f72317e5cc29
- network: running — https://app.devin.ai/sessions/8f214f6082a04381b3c3c24a3f9710ca

_Generated by swarm-md for C:\Users\Administrator\repos\swarm-md\demo\memory-repo\swarms\checkout-slow_