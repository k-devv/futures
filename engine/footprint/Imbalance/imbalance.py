"""
================================================================================
 Imbalance · imbalance.py  -  resting size around the price, read per bar
================================================================================
 WHAT   : IMBALANCE is the order-book imbalance sitting around the price, sampled
          across a bar. It is the present tense of absorption:

              BALLAST     positions that STAYED during the bar (history)
              IMBALANCE   money STILL RESTING there right now (present)

 WHY    : A footprint can show a fight and a bar can show that positions stayed,
          while the book has already been pulled. IMBALANCE catches that:

              absorption + BALLAST up + imbalance positive   the defender is there
              absorption + BALLAST up + imbalance negative   the defender left

          It updates every 10 s, so it warns while the bar is still forming -
          before the close confirms anything.

 HOW IT IS MEASURED
          GET /fapi/v1/depth?limit=100        weight 5, polled every POLL_SECONDS

          Take the mid price, keep every bid at or below it within BAND_USD, every
          ask at or above it within BAND_USD, value both sides in USDT, then

              imbalance = (bids - asks) / (bids + asks)        -1 .. +1

          +0.12  twelve percent more money resting on the bid side
          -0.18  eighteen percent more on the ask side

          limit=100 reaches roughly 1 USD around the price. It is the smallest
          depth that still covers a level 0.3 USD away without paying for 500 rows.

 COST   : weight 5 every 10 s = 30 weight a minute. Binance allows 2400.
          That is 1.25% of the budget for the whole book context.

 WHAT IT CANNOT DO
          There is no historical endpoint for the book at a price level.
          Binance's bookDepth archive stores depth by percentage from the mid,
          not around a chosen level, so it cannot backfill this honestly.
          Bars that closed before this process started therefore carry
          imbalance = None, and the page draws nothing for them. Never a zero.
================================================================================
"""

import json
import threading
import time
import urllib.request

MARKET = "https://fapi.binance.com"
DEPTH = "/fapi/v1/depth"

POLL_SECONDS = 10
WINDOW_MS = 5 * 60 * 1000
BAND_USD = 0.30        # how far around the price we count resting money
DEPTH_LIMIT = 100      # ~1 USD each side at BNB prices

_lock = threading.Lock()
_samples = {}          # window_start_ms -> [{"t": ms, "imbalance": float, "bids": float, "asks": float}]
_thread = None


def _read_book(symbol):
    """
    One depth snapshot, reduced to the numbers we keep.

    Input   symbol
    Output  {"t": epoch_ms, "mid": float, "bids": float, "asks": float,
             "imbalance": float}   or None when the call fails

    Weight 5. Failure returns None and the caller simply has no sample: a dead
    book read must never stop the poller or the chart.
    """
    try:
        url = f"{MARKET}{DEPTH}?symbol={symbol}&limit={DEPTH_LIMIT}"
        with urllib.request.urlopen(url, timeout=10) as response:
            book = json.loads(response.read())

        best_bid = float(book["bids"][0][0])
        best_ask = float(book["asks"][0][0])
        mid = (best_bid + best_ask) / 2

        bids = sum(float(price) * float(qty) for price, qty in book["bids"]
                   if mid - BAND_USD <= float(price) <= mid)
        asks = sum(float(price) * float(qty) for price, qty in book["asks"]
                   if mid <= float(price) <= mid + BAND_USD)
        total = bids + asks

        return {
            "t": int(book.get("T") or time.time() * 1000),
            "mid": round(mid, 4),
            "bids": round(bids, 2),
            "asks": round(asks, 2),
            "imbalance": round((bids - asks) / total, 4) if total else 0.0,
        }
    except Exception:
        return None


def _poll_loop(symbol):
    """
    The background loop: one snapshot every POLL_SECONDS, filed by window.

    Keeps three windows, which is enough for the forming bar and the two before
    it, and keeps memory flat forever.
    """
    while True:
        sample = _read_book(symbol)
        if sample:
            window = (sample["t"] // WINDOW_MS) * WINDOW_MS
            with _lock:
                _samples.setdefault(window, []).append(sample)
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
    global _thread
    with _lock:
        if _thread and _thread.is_alive():
            return
        _thread = threading.Thread(target=_poll_loop, args=(symbol,), daemon=True)
        _thread.start()


def from_samples(window_start):
    """
    IMBALANCE for a window we polled ourselves.

    Input   window_start, epoch ms aligned to 5 minutes
    Output  {"open", "close", "change", "average", "samples", "source": "poll"}
            or None when the window has no samples

    open / close are the first and last imbalance of the window, change is
    close - open, average is the mean across the window's samples. A window with
    a single sample returns change 0 and samples 1 - visible, not hidden.
    """
    with _lock:
        samples = list(_samples.get(window_start, []))

    if not samples:
        return None

    first, last = samples[0], samples[-1]
    values = [sample["imbalance"] for sample in samples]

    return {
        "open": round(first["imbalance"], 4),
        "close": round(last["imbalance"], 4),
        "change": round(last["imbalance"] - first["imbalance"], 4),
        "average": round(sum(values) / len(values), 4),
        "samples": len(samples),
        "source": "poll",
    }


def attach(bars):
    """
    Put IMBALANCE on each bar.

    Input   bars, list of bar dicts each with "t" (window start)
    Output  the same list, each bar with bar["imbalance"] = {...} or None

    There is no history to fall back on: the book at a price level is not
    archived by Binance. Bars older than this process get None, and the page
    shows nothing rather than inventing a number.
    """
    for bar in bars:
        bar["imbalance"] = from_samples(bar["t"])
    return bars


def summary():
    """
    Health line: how many windows are held and whether the poller is alive.

    Output  {"windows": int, "polling": bool}
    """
    with _lock:
        return {"windows": len(_samples), "polling": bool(_thread and _thread.is_alive())}
