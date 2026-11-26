"""
================================================================================
 engine/footprint/server.py  -  tape -> 5m bars -> one JSON -> the page
================================================================================
 WHAT   : Runs the live tape, groups the fills into 5-minute windows, and answers
          /api/footprint with the bars. It also serves the app files, so one
          command runs the whole desk.
 WHY    : The page must never touch Binance. It asks for bars, it gets bars.
          No database, no second source of truth, no aggregation on the client.
 WHERE  : Futures/engine/footprint
 SCALE  : Bars are rebuilt from raw trades with bars.bars_from_trades(), so the
          exact same code that reads history reads the live tape.

    python engine/footprint/server.py        ->  http://127.0.0.1:8320
"""

import asyncio
import json
import os
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import bars as footprint
import tape

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(os.path.dirname(HERE)), "app")
PORT = int(os.environ.get("FOOTPRINT_PORT") or 8320)

WINDOW_MS = 5 * 60 * 1000       # 5m bars
KEEP = 40                       # finished bars kept for the chart
CONTENT_TYPES = {"html": "text/html; charset=utf-8", "js": "text/javascript; charset=utf-8",
                 "css": "text/css; charset=utf-8", "json": "application/json",
                 "svg": "image/svg+xml", "png": "image/png"}

_lock = threading.Lock()
_state = {
    "window": None,             # start ms of the window being built
    "trades": [],               # raw fills of that window
    "finished": [],             # bars, oldest first
    "lastFill": 0,
    "fills": 0,
}


def _window_of(ms):
    return (ms // WINDOW_MS) * WINDOW_MS


def on_trade(price, qty, buyer_maker, ms):
    """Called for every fill. Cheap: append, and close the window when it rolls."""
    window = _window_of(ms)
    closed = None

    with _lock:
        if _state["window"] is None:
            _state["window"] = window

        if window != _state["window"]:
            closed = _finish_locked()
            _state["window"] = window
            _state["trades"] = []

        _state["trades"].append((price, qty, buyer_maker, ms))
        _state["lastFill"] = ms
        _state["fills"] += 1

    if closed:
        print(f"bar closed  {time.strftime('%H:%M', time.localtime(closed['t'] / 1000))}  "
              f"delta {closed['delta']:+.2f}  volume {closed['volume']:.2f}", flush=True)


def _verify(bar):
    """
    Ask Binance for the same 5m kline and compare. Runs after the bar freezes, in
    its own thread, so the tape never waits for it.

        delta = 2 * takerBuy - volume        (verified: matches our bars exactly)
    """
    url = ("https://fapi.binance.com/fapi/v1/klines"
           f"?symbol={tape.SYMBOL}&interval=5m&startTime={bar['t']}&limit=1")
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            kline = json.loads(response.read())[0]
    except Exception:
        bar["verified"] = None
        return

    volume = float(kline[5])
    delta = round(2 * float(kline[9]) - volume, 4)

    with _lock:
        bar["verified"] = abs(bar["volume"] - volume) <= 0.01 and abs(bar["delta"] - delta) <= 0.01
        bar["klineVolume"] = round(volume, 4)

    if not bar["verified"]:
        print(f"VERIFY MISMATCH {bar['time']} ours {bar['volume']:.2f}/{bar['delta']:+.2f} "
              f"kline {volume:.2f}/{delta:+.2f}", flush=True)


def _verify_all(seeded):
    """Check the seeded bars against their klines in the background, oldest first."""
    for bar in seeded:
        _verify(bar)


def _finish_locked():
    """Build the bar from the window's trades, keep it, and return it."""
    if not _state["trades"]:
        return None
    made = footprint.bars_from_trades(_state["trades"], WINDOW_MS)
    if not made:
        return None
    bar = made[0]
    bar["time"] = time.strftime("%H:%M", time.localtime(bar["t"] / 1000))
    bar.pop("rows_raw", None)
    bar["verified"] = None            # set by _verify() a moment later
    _state["finished"].append(bar)
    threading.Thread(target=_verify, args=(bar,), daemon=True).start()
    _state["finished"] = _state["finished"][-KEEP:]
    _state["trades"] = []
    return bar


def backfill(windows=30):
    """
    Seed the chart with the last finished bars, straight from Binance's tape.

    One public call per 5m window (aggTrades, 1000 rows is a full window for BNB),
    rebuilt by the same bars_from_trades() the live path uses.
    """
    now = int(time.time() * 1000)
    forming = _window_of(now)      # this window belongs to the live tape, not the backfill
    seeded = []

    for step in range(windows, 0, -1):
        start = forming - (step + 1) * WINDOW_MS   # only windows that have closed
        url = ("https://fapi.binance.com/fapi/v1/aggTrades"
               f"?symbol={tape.SYMBOL}&startTime={start}&endTime={start + WINDOW_MS - 1}&limit=1000")
        try:
            with urllib.request.urlopen(url, timeout=15) as response:
                trades = json.loads(response.read())
        except Exception:
            continue

        if not trades:
            continue

        made = footprint.bars_from_trades(
            [(float(t["p"]), float(t["q"]), bool(t["m"]), int(t["T"])) for t in trades],
            WINDOW_MS,
        )
        if not made:
            continue

        bar = made[0]
        bar["time"] = time.strftime("%H:%M", time.localtime(bar["t"] / 1000))
        seeded.append(bar)

    with _lock:
        _state["finished"] = seeded[-KEEP:]

    print(f"backfilled {len(seeded)} bars", flush=True)
    threading.Thread(target=_verify_all, args=(list(seeded[-KEEP:]),), daemon=True).start()


def snapshot():
    """The chart's whole world: finished bars plus the one being built."""
    with _lock:
        finished = list(_state["finished"])

        current = None
        if _state["trades"]:
            made = footprint.bars_from_trades(_state["trades"], WINDOW_MS)
            if made:
                current = made[0]
                current["time"] = time.strftime("%H:%M", time.localtime(current["t"] / 1000))
                current["current"] = True

        return {
            "symbol": tape.SYMBOL,
            "window": _window_of(_state["window"] or 0),
            "bars": finished,
            "current": current,
            "live": bool(_state["lastFill"]) and (time.time() * 1000 - _state["lastFill"] < 20000),
            "fills": _state["fills"],
        }


def run_tape():
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

        if path == "/api/footprint":
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


if __name__ == "__main__":
    backfill()
    threading.Thread(target=run_tape, daemon=True).start()
    print(f"FOOTPRINT  http://127.0.0.1:{PORT}  (/api/footprint + app)", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
