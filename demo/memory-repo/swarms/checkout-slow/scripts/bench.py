"""The swarm's shared measuring stick: hit /checkout N times, print stats.

Every agent measures with THIS script so numbers compare.
Usage: python demo/app/bench.py [n=60]
"""

import statistics
import sys
import time
import urllib.request

N = int(sys.argv[1]) if len(sys.argv) > 1 else 60
times = []
for _ in range(N):
    t = time.time()
    urllib.request.urlopen("http://127.0.0.1:8765/checkout").read()
    times.append(time.time() - t)

times.sort()
p50 = statistics.median(times)
p99 = times[int(len(times) * 0.99) - 1]
print(f"n={N}  median={p50*1000:.0f}ms  p99={p99*1000:.0f}ms  max={times[-1]*1000:.0f}ms")
