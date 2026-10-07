"""demo checkout server — has a real, findable slowdown.

Run:  python demo/app/server.py   (serves on :8765)
Hit:  python swarms/checkout-slow/scripts/bench.py 60

The p99 is ~600ms+ while the median is ~15ms. Why? `PriceCache.refresh()`
rebuilds the whole price table every 4 s under ONE write lock — every request
that arrives during a rebuild waits behind the lock. That is the planted bug
the swarm is meant to find.
"""

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

PRICES = {f"sku-{i}": round(9.99 + i * 0.37, 2) for i in range(50_000)}
LOG = os.path.join(os.path.dirname(__file__), "access.log")


class PriceCache:
    REFRESH_EVERY = 4.0   # seconds between rebuilds
    REBUILD_COST = 0.50   # seconds the write lock is held each rebuild
    READ_COST = 0.004     # simulated row fetch, per get(), under the lock

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._table = dict(PRICES)
        self._building = False
        threading.Thread(target=self._refresher, daemon=True).start()

    def _refresher(self) -> None:
        while True:
            time.sleep(self.REFRESH_EVERY)
            self.refresh()

    def refresh(self) -> None:
        # BUG: rebuilds the whole table under one write lock, and callers
        # queue behind it — a classic lock-convoy tail.
        with self._lock:
            self._building = True
            try:
                time.sleep(self.REBUILD_COST)
                self._table = dict(PRICES)
            finally:
                self._building = False

    def get(self, sku: str) -> float:
        with self._lock:
            time.sleep(self.READ_COST)
            return self._table[sku]


CACHE = PriceCache()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        start = time.time()
        if self.path.startswith("/checkout"):
            # 3 price reads per checkout, each under the shared lock
            total = sum(CACHE.get(f"sku-{i % 1000}") for i in range(3))
            body = json.dumps({"total": round(total, 2)}).encode()
            self.send_response(200)
        else:
            body = b"ok"
            self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        if self.path.startswith("/checkout"):
            try:
                with open(LOG, "a") as f:
                    f.write(f"{time.time():.3f} {time.time()-start:.3f}\n")
            except OSError:
                pass

    def log_message(self, *args) -> None:  # quiet
        pass


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
