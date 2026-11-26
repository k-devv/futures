"""
================================================================================
 engine/footprint/server.py  -  tape -> 5m bars -> one JSON -> the page
================================================================================
 WHAT   : The forming 5m bar is built from the live socket. When a window ends,
          that bar is fetched from Binance's aggregated trades and stored. The
          last 30 closed bars are backfilled the same way at startup.
 WHY    : The live bar has to breathe; a closed bar has to be exact. Keeping the
          two paths separate means a missed message can never reach a finished
          bar - the closed bar is simply Binance's own record.
 WHERE  : Futures/engine/footprint
 SCALE  : Bars are always built by bars.bars_from_trades(), whichever path feeds it.

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
KEEP = 30                       # closed bars kept for the chart
AGG = "https://fapi.binance.com/fapi/v1/aggTrades"
CONTENT_TYPES = {"html": "text/html; charset=utf-8", "js": "text/javascript; charset=utf-8",
                 "css": "text/css; charset=utf-8", "json": "application/json",
                 "svg": "image/svg+xml", "png": "image/png"}

_lock = threading.Lock()
_state = {
    "window": None,             # start ms of the window being built
    "trades": [],               # fills of that window, from the socket
    "finished": [],             # closed bars from Binance, oldest first
    "lastFill": 0,
    "fills": 0,
}


# ------------------------------------------------------------------ tape
def _window_of(ms):
    return (ms // WINDOW_MS) * WINDOW_MS


def on_trade(price, qty, buyer_maker, ms):
    """Every fill: append to the forming window, and close it when the clock rolls."""
    window = _window_of(ms)

    with _lock:
        if _state["window"] is None:
            _state["window"] = window

        if window != _state["window"]:
            previous = _state["window"]
            _state["window"] = window
            _state["trades"] = []
            threading.Thread(target=_close_bar, args=(previous,), daemon=True).start()

        _state["trades"].append((price, qty, buyer_maker, ms))
        _state["lastFill"] = ms
        _state["fills"] += 1


def run_tape():
    async def main():
        await tape.stream(on_trade, quiet=True)
    asyncio.run(main())


# ------------------------------------------------------------------ binance
def fetch_agg(start_ms, end_ms):
    """
    Every aggregated trade in a window, paginated.

    One call returns at most 1000 rows and a busy 5m window can exceed that, so ask
    again from just after the last row until the window is covered.
    """
    rows = []
    cursor = start_ms

    while cursor <= end_ms:
        url = f"{AGG}?symbol={tape.SYMBOL}&startTime={cursor}&endTime={end_ms}&limit=1000"
        try:
            with urllib.request.urlopen(url, timeout=15) as response:
                page = json.loads(response.read())
        except Exception:
            break

        if not page:
            break

        rows.extend(page)
        if len(page) < 1000:
            break

        last = int(page[-1]["T"])
        if last <= cursor:
            break
        cursor = last + 1

    return rows


def _bar_from(trades, window_start):
    made = footprint.bars_from_trades(
        [(float(t["p"]), float(t["q"]), bool(t["m"]), int(t["T"])) for t in trades],
        WINDOW_MS,
    )
    if not made:
        return None
    bar = made[0]
    bar["time"] = time.strftime("%H:%M", time.localtime(bar["t"] / 1000))
    bar["source"] = "rest"
    return bar


def _store(bar):
    with _lock:
        _state["finished"] = sorted(_state["finished"] + [bar], key=lambda item: item["t"])[-KEEP:]


def _close_bar(window_start, attempts=3):
    """A window ended: the finished bar is Binance's record, not ours."""
    for attempt in range(attempts):
        bar = _bar_from(fetch_agg(window_start, window_start + WINDOW_MS - 1), window_start)
        if bar:
            _store(bar)
            print(f"bar closed  {bar['time']}  delta {bar['delta']:+.2f}  volume {bar['volume']:.2f}", flush=True)
            _fill_gaps()
            return bar
        time.sleep(0.5 * (attempt + 1))

    print(f"bar missing {window_start}", flush=True)
    return None


def _fill_gaps():
    """If a close was missed (socket silent, network error), fetch what is missing."""
    forming = _window_of(int(time.time() * 1000))

    with _lock:
        stored = {bar["t"] for bar in _state["finished"]}
        last = max(stored) if stored else forming - WINDOW_MS

    start = last + WINDOW_MS
    while start < forming:
        if start not in stored:
            bar = _bar_from(fetch_agg(start, start + WINDOW_MS - 1), start)
            if bar:
                _store(bar)
                print(f"gap filled  {bar['time']}  volume {bar['volume']:.2f}", flush=True)
        start += WINDOW_MS


def backfill():
    """Seed the chart with the last closed bars, one REST window each."""
    forming = _window_of(int(time.time() * 1000))
    seeded = []

    for step in range(KEEP, -1, -1):   # includes the window that just closed
        start = forming - (step + 1) * WINDOW_MS
        bar = _bar_from(fetch_agg(start, start + WINDOW_MS - 1), start)
        if bar:
            seeded.append(bar)

    with _lock:
        _state["finished"] = seeded[-KEEP:]

    print(f"backfilled {len(seeded)} bars", flush=True)


def seed_current():
    """
    Fill in the running window before the socket opens.

    Only used for the forming bar, and only to avoid showing a bar that starts at
    the moment we happened to boot.
    """
    now = int(time.time() * 1000)
    start = _window_of(now)
    trades = fetch_agg(start, now)
    if not trades:
        return

    seeded = [(float(t["p"]), float(t["q"]), bool(t["m"]), int(t["T"])) for t in trades]

    with _lock:
        _state["window"] = start
        _state["trades"] = seeded

    print(f"seeded the running window with {len(seeded)} fills", flush=True)


# ------------------------------------------------------------------ output
def _dedupe(trades):
    """Exact duplicates only: same price, size, side and millisecond."""
    seen = set()
    unique = []
    for trade in trades:
        if trade in seen:
            continue
        seen.add(trade)
        unique.append(trade)
    return unique


def snapshot():
    """The chart's whole world: closed bars from Binance, plus the forming one."""
    with _lock:
        finished = list(_state["finished"])

        current = None
        if _state["trades"]:
            made = footprint.bars_from_trades(_dedupe(_state["trades"]), WINDOW_MS)
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
        }


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
    seed_current()
    threading.Thread(target=run_tape, daemon=True).start()
    print(f"FOOTPRINT  http://127.0.0.1:{PORT}  (/api/footprint + app)", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
