# Agent: network

- Area: network
- Notes go here as the agent works [added: 2026-10-07]

## Method
- Server: `python demo/app/server.py` backgrounded, 127.0.0.1:8765.
- Baseline: shared `bench.py 60` from demo/memory-repo.
- Probes (scratch scripts, not committed): raw `socket.create_connection` timing; GET `/` vs `/checkout` via urllib; manual HTTP/1.0 request with connect-phase vs response-phase split; threaded concurrent clients at C=4 and C=16.

## Measured (solo client)
- bench.py 60: median=14ms p99=450ms max=470ms.
- TCP connect, n=295 spanning 3 rebuilds: median=0.2ms p99=0.5ms max=2.1ms.
- GET `/` (no lock touched), n=200 spanning 2 rebuilds: median=0.9ms p99=1.5ms max=11.9ms.
- `/checkout` split, n=60: connect p99=0.3ms; response p99=445.8ms.
- access.log server-side vs client: median 14.0 vs 14.4ms, p99 449 vs 446ms, max 469 vs 469.6ms — transport adds ~0ms.
- Wire: HTTP/1.0, Server: BaseHTTP/0.6, Content-Length 16, close per request.

## Measured (concurrent)
- C=4: p99=505ms max=516ms.
- C=16: connect p99=2017ms max=2020ms; response p99=580ms; total p99=2090ms ≈ reported ~2.4s. 0 errors.

## Verdict
- Transport does NOT explain the tail at solo load: connect is sub-ms even mid-rebuild, payloads are 16 bytes, client time == server time.
- Transport DOES explain the multi-second extreme under concurrency: `http.server.HTTPServer` is single-threaded; while a handler sits in the ~0.5s PriceCache rebuild stall the accept loop stops, the listen backlog (request_queue_size=5) overflows, client SYNs are dropped, and Windows retransmits after ~2s → connect phase alone hits p99≈2.0s.
- So: primary cause is the app-layer lock convoy (cache's area); the transport contribution is the SYN-drop retransmit amplifier that turns a ~0.5s stall into a ~2.4s tail when concurrent clients pile up.
