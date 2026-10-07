"""demo checkout server — has a real, findable slowdown.

Run:  python demo/app/server.py  (serves on :8765)
Hit:  curl -s -o /dev/null -w '%{time_total}' localhost:8765/checkout

The p99 is ~2.4s while the median is ~80ms. Why? `PriceCache.refresh()`
rebuilds a 2 GB-equivalent in-memory table every 10 s under a write lock —
every Nth request pays ~400ms, and occasionally a double rebuild stacks to
seconds. That is the planted bug the swarm is meant to find.
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

PRICES = {f"sku-{i}": round(9.99 + i * 0.37, 2) for i in range(50_000)}


class PriceCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._table = dict(PRICES)
        threading.Thread(target=self._refresher, daemon=True).start()

    def _refresher(self) -> None:
        while True:
            time.sleep(10)
            self.refresh()

    def refresh(self) -> None:
        # BUG: rebuilds the whole table under one write lock.
        with self._lock:
            time.sleep(0.40)  # simulates the heavy rebuild
            self._table = dict(PRICES)

    def get(self, sku: str) -> float:
        with self._lock:
            return self._table[sku]


CACHE = PriceCache()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        start = time.time()
        if self.path.startswith("/checkout"):
            total = sum(CACHE.get(f"sku-{i % 1000}") for i in range(3))
            body = json.dumps({"total": round(total, 2)}).encode()
            self.send_response(200)
        else:
            body = b"ok"
            self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        elapsed = time.time() - start
        if self.path.startswith("/checkout"):
            with open("demo/app/access.log", "a") as f:
                f.write(f"{time.time():.3f} {elapsed:.3f}\n")

    def log_message(self, *args) -> None:  # quiet
        pass


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
