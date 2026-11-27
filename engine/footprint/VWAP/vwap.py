"""
================================================================================
 VWAP · vwap.py  -  where the session sits, in one number
================================================================================
 WHAT   : The daily VWAP, the weekly VWAP, and the session and previous-day
          extremes, computed from Binance klines. This is the LOCATION half of
          the footprint checklist: is this bar at a level that matters, or in the
          middle of nowhere?

 WHY    : Absorption in the middle of a range is noise. Absorption at VWAP, at
          the session high, at the previous day's extreme, or at a round number
          is a decision point. Without this, the footprint tells you a fight
          happened but not whether anyone cared.

 HOW IT IS COMPUTED
          VWAP = sum(typical price * volume) / sum(volume)

          typical price = (high + low + close) / 3   over each 1m kline,
          accumulated from the start of the session (00:00 UTC) to now.

          The weekly VWAP is the same arithmetic from Monday 00:00 UTC, built on
          15m klines because seven days of 1m rows is more than one call returns.

          Both use Binance's own volume, so VWAP is the market's average price,
          not ours.

 COST   : two kline calls, cached for CACHE_SECONDS. Weight ~10 a minute.
          Refreshing every second would be waste: VWAP barely moves late in a day.

 WHAT IT IS NOT
          Not an indicator to trade on its own. It is the map: trade AT it, not
          BECAUSE of it.
================================================================================
"""

import json
import time
import urllib.request

MARKET = "https://fapi.binance.com"
KLINES = "/fapi/v1/klines"

CACHE_SECONDS = 60
DAY_MS = 24 * 60 * 60 * 1000
WEEK_MS = 7 * DAY_MS

_cache = {"at": 0, "symbol": None, "levels": None}


def _klines(symbol, interval, start_ms, limit=1500):
    """
    Raw klines from Binance, oldest first.

    Input   symbol, interval ("1m", "15m"), start_ms, limit (<= 1500)
    Output  list of rows as Binance returns them, or [] on failure
    """
    try:
        url = (f"{MARKET}{KLINES}?symbol={symbol}&interval={interval}"
               f"&startTime={start_ms}&limit={limit}")
        with urllib.request.urlopen(url, timeout=15) as response:
            return json.loads(response.read())
    except Exception:
        return []


def _utc_midnight(now_ms):
    """Start of the current UTC day. Binance sessions are UTC, not local."""
    return (now_ms // DAY_MS) * DAY_MS


def _utc_monday(now_ms):
    """Start of the current UTC week (Monday 00:00). 1970-01-01 was a Thursday."""
    days_since_epoch = now_ms // DAY_MS
    return (days_since_epoch - ((days_since_epoch + 3) % 7)) * DAY_MS


def _vwap(rows):
    """
    Volume-weighted average price over a set of klines.

    Input   rows as returned by _klines
    Output  (vwap, high, low) or (None, None, None) when there are no rows

    high and low are the extremes of the same window, which is what makes the
    session high/low and the previous-day extremes free.
    """
    money = 0.0
    volume = 0.0
    high = None
    low = None

    for row in rows:
        bar_high = float(row[2])
        bar_low = float(row[3])
        bar_close = float(row[4])
        bar_volume = float(row[5])

        typical = (bar_high + bar_low + bar_close) / 3
        money += typical * bar_volume
        volume += bar_volume

        high = bar_high if high is None else max(high, bar_high)
        low = bar_low if low is None else min(low, bar_low)

    if not volume:
        return None, high, low

    return round(money / volume, 4), high, low


def levels(symbol, force=False):
    """
    The location set for the current session, cached for CACHE_SECONDS.

    Input   symbol, force to bypass the cache
    Output  {
              "vwap": float,            daily VWAP, the line that matters most
              "weekly_vwap": float,     the larger context
              "session_high": float,
              "session_low": float,
              "prev_day_high": float,
              "prev_day_low": float,
              "round": float,           nearest round 0.5 to the last close
              "at": epoch_ms
            }

    Every value comes from Binance klines. If a call fails, that field is None
    and the caller shows nothing rather than guessing.
    """
    now = int(time.time() * 1000)
    if not force and _cache["levels"] and _cache["symbol"] == symbol and now - _cache["at"] < CACHE_SECONDS:
        return _cache["levels"]

    day_start = _utc_midnight(now)
    week_start = _utc_monday(now)

    day_rows = _klines(symbol, "1m", day_start)
    prev_rows = _klines(symbol, "1m", day_start - DAY_MS, limit=1440)
    week_rows = _klines(symbol, "15m", week_start, limit=700)

    vwap, session_high, session_low = _vwap(day_rows)
    weekly_vwap, _, _ = _vwap(week_rows)
    _, prev_high, prev_low = _vwap(prev_rows)

    last_close = float(day_rows[-1][4]) if day_rows else None
    round_level = round(last_close / 0.5) * 0.5 if last_close else None

    result = {
        "vwap": vwap,
        "weekly_vwap": weekly_vwap,
        "session_high": session_high,
        "session_low": session_low,
        "prev_day_high": prev_high,
        "prev_day_low": prev_low,
        "round": round_level,
        "at": now,
    }

    _cache.update(at=now, symbol=symbol, levels=result)
    return result


def nearest(price, values):
    """
    The closest level to a price, and how far away it is as a fraction of price.

    Input   price, the dict returned by levels()
    Output  (name, value, distance_fraction) - name is None when nothing is known

    The checklist's LOCATION test uses this: 0.12% is "at the level", 0.25% is
    "near it", anything further is no-man's land.
    """
    if price is None:
        return None, None, None

    options = [
        ("vwap", values.get("vwap")),
        ("weekly vwap", values.get("weekly_vwap")),
        ("session high", values.get("session_high")),
        ("session low", values.get("session_low")),
        ("prev day high", values.get("prev_day_high")),
        ("prev day low", values.get("prev_day_low")),
        ("round", values.get("round")),
    ]
    options = [(name, value) for name, value in options if value]

    if not options:
        return None, None, None

    name, value = min(options, key=lambda item: abs(item[1] - price))
    return name, value, abs(value - price) / price


def summary(symbol):
    """
    A compact line for the status strip: VWAP and where price sits relative to it.

    Output  {"vwap": float, "bias": "long"|"short"|None, "weekly_vwap": float}
    """
    values = levels(symbol)
    vwap = values.get("vwap")
    price = values.get("round")          # only the last close is stored; bias uses it

    if vwap is None or price is None:
        return {"vwap": vwap, "weekly_vwap": values.get("weekly_vwap"), "bias": None}

    return {
        "vwap": vwap,
        "weekly_vwap": values.get("weekly_vwap"),
        "bias": "long" if price >= vwap else "short",
    }
