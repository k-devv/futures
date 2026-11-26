"""
================================================================================
 engine/footprint/live.py  -  the tape, served to the page
================================================================================
 WHAT   : Runs tape.py in a background thread, keeps the current minute and the
          last trades in memory, and serves them as JSON on /api/tape.
          The same process also serves the app files, so one command runs it.
 WHY    : The page must never talk to Binance. It reads one small JSON and draws
          exactly what the tape saw - no signals, no open interest, no opinion.
 WHERE  : Futures/engine/footprint
 SCALE  : One symbol. Add a field to snapshot() when the page needs it.

    python engine/footprint/live.py          ->  http://127.0.0.1:8310
"""

import asyncio
import collections
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import tape

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(os.path.dirname(HERE)), "app")   # Futures/app
PORT = int(os.environ.get("TAPE_PORT") or 8310)
KEEP = 80                      # trades kept for the list
CONTENT_TYPES = {"html": "text/html; charset=utf-8", "js": "text/javascript; charset=utf-8",
                 "css": "text/css; charset=utf-8", "json": "application/json",
                 "svg": "image/svg+xml", "png": "image/png"}

_lock = threading.Lock()
_state = {
    "connected": False,
    "price": 0.0,
    "minute": None,          # minute key
    "buys": 0.0,
    "sells": 0.0,
    "trades": 0,
    "last": None,            # {price, qty, side, ms}
    "list": collections.deque(maxlen=KEEP),
    "updated": 0,
}


def on_trade(price, qty, buyer_maker, ms):
    """Called by the tape for every fill. Cheap on purpose."""
    minute = ms // 60000
    with _lock:
        if minute != _state["minute"]:
            _state.update(minute=minute, buys=0.0, sells=0.0, trades=0)
        if buyer_maker:
            _state["sells"] += qty
        else:
            _state["buys"] += qty
        _state["trades"] += 1
        _state["price"] = price
        _state["connected"] = True
        _state["updated"] = int(time.time() * 1000)
        _state["last"] = {"price": price, "qty": qty,
                          "side": "sell" if buyer_maker else "buy", "ms": ms}
        _state["list"].appendleft({"price": price, "qty": qty,
                                   "side": "sell" if buyer_maker else "buy", "ms": ms})


def snapshot():
    with _lock:
        minute = _state["minute"]
        buys, sells = _state["buys"], _state["sells"]
        return {
            "connected": _state["connected"],
            "price": _state["price"],
            "minute": minute * 60000 if minute else None,
            "volume": round(buys + sells, 4),
            "delta": round(buys - sells, 4),
            "trades": _state["trades"],
            "last": _state["last"],
            "list": list(_state["list"]),
            "updated": _state["updated"],
        }


def run_tape():
    """tape.stream() is asyncio; run it in this thread with its own loop."""
    async def main():
        await tape.stream(on_trade, quiet=True)
    asyncio.run(main())


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/api/tape":
            self._send(200, json.dumps(snapshot()).encode())
            return

        relative = "app/index.html" if path in ("/", "") else path.lstrip("/")
        full = os.path.normpath(os.path.join(os.path.dirname(APP), relative))
        if not full.startswith(APP) or not os.path.isfile(full):
            self._send(404, b"not found", "text/plain")
            return

        ctype = CONTENT_TYPES.get(full.rsplit(".", 1)[-1], "application/octet-stream")
        with open(full, "rb") as handle:
            self._send(200, handle.read(), ctype)

    def log_message(self, *args):
        pass


def main():
    threading.Thread(target=run_tape, daemon=True).start()
    threading.Thread(target=_staleness, daemon=True).start()
    print(f"TAPE  http://127.0.0.1:{PORT}  (app + /api/tape)", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


def _staleness():
    """If no trade arrives for 20 s, say so - a silent tape must never look live."""
    while True:
        time.sleep(5)
        with _lock:
            if _state["updated"] and time.time() * 1000 - _state["updated"] > 20000:
                _state["connected"] = False


if __name__ == "__main__":
    main()
