"""
================================================================================
 BALLAST · ballast.py  -  open interest, read per bar
================================================================================
 WHAT   : BALLAST is the change in open interest across one 5m bar. It answers the
          one question the footprint cannot: the footprint shows that size traded
          at a price, BALLAST shows whether that size stayed there or was handed
          over and closed.

              price flat + BALLAST up      positions were opened and held
                                           -> somebody is absorbing
              price flat + BALLAST down    positions were closed
                                           -> churn, the level is hollow
              price moving + BALLAST up    new money pushing the move
              price moving + BALLAST down  old money leaving, the move is a squeeze

 WHY    : Absorption without open interest is a guess. With it, "heavy row" becomes
          "heavy row and the size is still standing there". That is the difference
          between a level worth risking on and a level that only looked busy.

 WHERE  : Futures/engine/footprint/BALLAST
          imported by engine/footprint/server.py, never by the page.

 HOW IT IS MEASURED
          Binance has no open-interest websocket, so there are two honest sources:

              1  GET /fapi/v1/openInterest      a live snapshot, weight 1
                 -> polled every POLL_SECONDS while the bar is forming

              2  GET /futures/data/openInterestHist   the official 5m series
                 -> used for bars that closed before we were running

          A bar's BALLAST is  last value in the window  -  first value in the window.
          Both numbers are Binance's; we only subtract them.

 PUBLICATION TIMES
          Binance publishes each 5m open-interest row roughly three minutes after
          the window closes. We stamp the FIRST time we see a row and keep it, so
          the number the chart shows is the moment the data actually arrived, not
          the moment we happened to refresh.

COST   : one weight-1 request every 10 s while running (~0.1 weight/s), and one
          history request per batch of bars that has no polled samples.
================================================================================
"""

import json
import os
import threading
import time
import urllib.request

MARKET = "https://fapi.binance.com"
NOW = "/fapi/v1/openInterest"
HIST = "/futures/data/openInterestHist"

POLL_SECONDS = 10
BAR_MS = 5 * 60 * 1000      # one snapshot every 10 s: 30 per bar, weight 30
WINDOW_MS = 5 * 60 * 1000

_lock = threading.Lock()
_samples = {}          # window_start_ms -> [{"t": ms, "oi": float}, ...]
_thread = None
_symbol = None


# ---------------------------------------------------- when a row was first seen
_SEEN_PATH = os.path.join(os.path.dirname(__file__), "seen.json")
_seen = {}


def _load_seen():
    """First-seen timestamps survive a restart, so 13:38 stays 13:38."""
    global _seen
    try:
        with open(_SEEN_PATH, encoding="utf-8") as handle:
            _seen = {int(key): int(value) for key, value in json.load(handle).items()}
    except Exception:
        _seen = {}


def _save_seen():
    try:
        with open(_SEEN_PATH, "w", encoding="utf-8") as handle:
            json.dump({str(key): value for key, value in _seen.items()}, handle)
    except Exception:
        pass


def note(rows):
    """
    Remember when each row was first seen. Called on every fetch.

    Input   rows from Binance (oldest first)
    Effect  stamps the rows we had not seen before and saves the file
    """
    now = int(time.time() * 1000)
    added = False

    for row in rows:
        if row["t"] not in _seen:
            _seen[row["t"]] = now
            added = True

    if added:
        _save_seen()


def published_at(row_time):
    """When we first saw that row, or None."""
    return _seen.get(int(row_time))


_load_seen()


# ------------------------------------------------------------------ primitives
def open_interest_now(symbol):
    """
    One live open-interest snapshot from Binance.

    Input   symbol, e.g. "BNBUSDT"
    Output  {"t": epoch_ms, "oi": float}  - t is Binance's own timestamp
    Cost    weight 1

    Raises nothing: a network failure returns None and the caller simply has no
    sample for that moment. Polling must never take the engine down.
    """
    try:
        url = f"{MARKET}{NOW}?symbol={symbol}"
        with urllib.request.urlopen(url, timeout=10) as response:
            payload = json.loads(response.read())
        return {"t": int(payload["time"]), "oi": float(payload["openInterest"])}
    except Exception:
        return None


def history(symbol, period="5m", limit=30):
    """
    The official open-interest series, one row per period.

    Input   symbol, period ("5m", "15m", "30m", "1h", ...), limit (<= 500)
    Output  [{"t": window_start_ms, "oi": float}, ...] oldest first
    Cost    weight 1, and the series only goes back 30 days

    Warning: Binance returns the OLDEST rows up to limit, not the newest. Ask for
    a large window and match by timestamp, never assume the last row is "now".

    Used for bars that closed before this process started, and for backfills.
    The 5m series gives the same numbers the live endpoint would have given us,
    just sampled by Binance instead of by us.
    """
    try:
        url = (f"{MARKET}{HIST}?symbol={symbol}&period={period}"
               f"&limit={min(limit, 500)}")
        with urllib.request.urlopen(url, timeout=15) as response:
            rows = json.loads(response.read())
        return [{"t": int(row["timestamp"]), "oi": float(row["sumOpenInterest"])} for row in rows]
    except Exception:
        return []


# ------------------------------------------------------------------ polling
def _poll_loop(symbol):
    """
    The background loop.

    Every POLL_SECONDS it takes one snapshot and files it under the window it
    belongs to. Nothing else. A failed poll is skipped, never retried in a spin -
    the next tick is the retry.
    """
    while True:
        sample = open_interest_now(symbol)
        if sample:
            window = (sample["t"] // WINDOW_MS) * WINDOW_MS
            with _lock:
                _samples.setdefault(window, []).append(sample)
                # keep memory flat: one bar is enough for the forming bar
                for key in [key for key in _samples if key < window - 3 * WINDOW_MS]:
                    _samples.pop(key, None)
        time.sleep(POLL_SECONDS)


def start(symbol):
    """
    Start polling once for the life of the process.

    Input   symbol
    Output  None
    Why     server.py calls this at boot; calling it twice is harmless.
    """
    global _thread, _symbol
    with _lock:
        _symbol = symbol
        if _thread and _thread.is_alive():
            return
        _thread = threading.Thread(target=_poll_loop, args=(symbol,), daemon=True)
        _thread.start()


# ------------------------------------------------------------------ per bar
def from_samples(window_start):
    """
    BALLAST for a window we polled ourselves.

    Input   window_start, epoch ms aligned to 5 minutes
    Output  {"open", "close", "change", "samples", "source": "poll"} or None

    "open" is the first snapshot inside the window, "close" the last. If we only
    caught one snapshot, the change is 0 and samples says 1 - visible, not hidden.
    """
    with _lock:
        samples = list(_samples.get(window_start, []))

    if not samples:
        return None

    first, last = samples[0], samples[-1]
    return {
        "open": round(first["oi"], 2),
        "close": round(last["oi"], 2),
        "change": round(last["oi"] - first["oi"], 2),
        "samples": len(samples),
        "source": "poll",
    }


def from_history(window_start, rows):
    """
    BALLAST for a window taken from the official 5m series.

    Input   window_start, epoch ms aligned to 5 minutes
              rows, the list returned by history()
    Output  {"open", "close", "change", "samples", "source": "hist"} or None

    The series has one row per period, so "open" is the row starting at this
    window and "close" is the next row's value - the boundary the window ended on.
    """
    for index, row in enumerate(rows):
        if row["t"] != window_start:
            continue
        if index + 1 >= len(rows):
            return None
        following = rows[index + 1]
        return {
            "open": round(row["oi"], 2),
            "close": round(following["oi"], 2),
            "change": round(following["oi"] - row["oi"], 2),
            "samples": 2,
            "source": "hist",
        }
    return None


def attach(bars, symbol):
    """
    Put BALLAST on each bar, preferring what we polled and falling back to Binance.

    Input   bars, list of bar dicts each with "t" (window start)
              symbol
    Output  the same list, each bar with bar["ballast"] = {...} or None

    Order of preference matters:
        polled samples  - taken while the bar was forming, the closest view
        official series - the same window, sampled by Binance
        None            - no data; the page draws nothing rather than a zero
    """
    if not bars:
        return bars

    # ONE source: Binance's own 5m open-interest series.
    # we do not poll our own snapshot any more - the endpoint is the truth, even
    # though it means the forming bar has no number until its row is published.
    rows = history(symbol, "5m", limit=500) if bars else []

    note(rows)                                # stamp any row we had not seen yet
    received = int(time.time() * 1000)

    for bar in bars:
        value = from_history(bar["t"], rows)
        if value:
            # the confirming row is the one after the bar
            value["received"] = published_at(bar["t"] + BAR_MS) or received
        bar["ballast"] = value
    return bars


def summary():
    """
    A tiny health block for the status line: how many windows we hold.

    Output  {"windows": int, "polling": bool}
    """
    with _lock:
        return {"windows": len(_samples), "polling": bool(_thread and _thread.is_alive())}
