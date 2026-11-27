"""
================================================================================
 engine/footprint/bars.py  -  the tape, bucketed into bars you can read
================================================================================
 WHAT   : Takes raw trades (price, size, buyer-maker flag, time) and returns one
          bar per minute: every 0.1 price row with its buy and sell volume, the
          delta, the POC and which side it printed on, and the bar's OHLC.
 WHY    : Everything we trade is decided from this: absorption needs rows,
          HELD/EATEN needs the next bar, POC needs the busiest row.
 WHERE  : Futures/engine/footprint
 SCALE  : Bucket size is a parameter. Nothing here knows about Binance or HTTP.
================================================================================

Run standalone on a CSV from data.binance.vision:

    python engine/footprint/bars.py data/BNBUSDT-aggTrades-2026-11-25.csv
"""

import csv
import time

BUCKET = 0.1          # the price row every trade is printed into
MIN_ROW = 0.5         # ignore rows smaller than this many coins


def _bucket(price):
    return round(round(price / BUCKET) * BUCKET, 6)


def bars_from_trades(trades, bar_ms=60000):
    """
    trades: iterable of (price, qty, is_buyer_maker, ms)
    bar_ms: 60000 for a 1m bar, 300000 for 5m - the caller decides
    returns: list of bars, oldest first.
    """
    minutes = {}
    for price, qty, buyer_maker, ms in trades:
        # a zero or negative price is never a real fill; one would stretch the
        # whole price grid to 0 and bury the chart
        if price <= 0 or qty <= 0:
            continue

        minute = ms // bar_ms
        bar = minutes.get(minute)
        if bar is None:
            bar = minutes[minute] = {
                "t": minute * bar_ms,
                "open": price, "high": price, "low": price, "close": price,
                "rows": {}, "buys": 0.0, "sells": 0.0, "trades": 0,
            }

        # taker lifted the ask = a buy; taker hit the bid = a sell
        side = "sell" if buyer_maker else "buy"
        row = bar["rows"].setdefault(_bucket(price), {"buy": 0.0, "sell": 0.0})
        row[side] += qty

        bar["high"] = max(bar["high"], price)
        bar["low"] = min(bar["low"], price)
        bar["close"] = price
        bar["trades"] += 1
        if side == "buy":
            bar["buys"] += qty
        else:
            bar["sells"] += qty

    out = []
    for minute in sorted(minutes):
        bar = minutes[minute]
        rows = {price: row for price, row in bar["rows"].items() if row["buy"] + row["sell"] >= MIN_ROW}

        poc, poc_side, poc_size = None, None, 0.0
        for price, row in rows.items():
            size = row["buy"] + row["sell"]
            if size > poc_size:
                poc, poc_side, poc_size = price, ("ask" if row["buy"] >= row["sell"] else "bid"), size

        out.append({
            "t": bar["t"],
            "open": bar["open"], "high": bar["high"], "low": bar["low"], "close": bar["close"],
            "buys": round(bar["buys"], 4),
            "sells": round(bar["sells"], 4),
            "delta": round(bar["buys"] - bar["sells"], 4),
            "volume": round(bar["buys"] + bar["sells"], 4),
            "trades": bar["trades"],
            "rows": rows,
            "poc": poc,
            "pocSide": poc_side,
            "pocSize": round(poc_size, 4),
            "range": round(bar["high"] - bar["low"], 6),
        })

    return out


def read_csv(path):
    """data.binance.vision aggTrades CSV -> the tuple stream bars_from_trades wants."""
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            yield float(row["price"]), float(row["quantity"]), row["is_buyer_maker"] == "true", int(row["transact_time"])


def absorption_candidates(bar, multiple=3.0):
    """
    A row is a candidate when size shows up at one price and the bar rejects it.

        touched       the price printed in this bar
        rejected      the close is away from it by more than max(bucket, 0.05%)
        heavy         the row is `multiple` times the median row of the bar
    """
    sizes = sorted((row["buy"] + row["sell"]) for row in bar["rows"].values())
    if len(sizes) < 3:
        return []

    median = sizes[len(sizes) // 2] or 0.01
    margin = max(BUCKET, bar["close"] * 0.0005)
    events = []

    for price, row in bar["rows"].items():
        size = row["buy"] + row["sell"]
        if size < median * multiple:
            continue
        if not (bar["low"] <= price <= bar["high"]):
            continue

        if bar["close"] >= price + margin:
            events.append({"t": bar["t"], "price": price, "side": "buy", "size": round(size, 3)})
        elif bar["close"] <= price - margin:
            events.append({"t": bar["t"], "price": price, "side": "sell", "size": round(size, 3)})

    return events


# ------------------------------------------------------------------ truth checks
def kline_delta(kline):
    """
    Binance's own per-minute delta, from the kline itself.

    kline[5] = total base volume, kline[9] = taker BUY base volume, so the taker
    SELL volume is the rest. Verified against aggTrades to 0.000 on live minutes:

        delta = 2 * takerBuy - volume

    This is the free check that our websocket did not drop anything.
    """
    volume = float(kline[5])
    taker_buy = float(kline[9])
    return {"volume": round(volume, 4), "takerBuy": round(taker_buy, 4),
            "delta": round(2 * taker_buy - volume, 4)}


def check_against_kline(bar, kline, tolerance=0.01):
    """Compare our bar with Binance's kline for the same minute."""
    theirs = kline_delta(kline)
    diff = round(bar["delta"] - theirs["delta"], 4)
    volume_diff = round(bar["volume"] - theirs["volume"], 4)
    return {
        "ok": abs(diff) <= tolerance and abs(volume_diff) <= tolerance,
        "delta_diff": diff,
        "volume_diff": volume_diff,
        "ours": bar["delta"],
        "theirs": theirs["delta"],
    }


def rpi_share(trades):
    """
    RPI = retail price improvement flow. aggTrades carries `nq` (quantity that is
    NOT RPI) beside `q`, so the difference is retail.

    Measured on BNB for several minutes: 0.0% - RPI is effectively absent here.
    Reported anyway, because it costs nothing and tells us when that changes.
    """
    total = sum(float(t["q"]) for t in trades)
    non_rpi = sum(float(t.get("nq", t["q"])) for t in trades)
    return round((total - non_rpi) / total, 4) if total else 0.0


# ------------------------------------------------------------------ context that is not the tape
def open_interest_per_bar(samples):
    """
    samples: list of (ms, openInterest) polled from /fapi/v1/openInterest.
    returns: {minute_ms: {"open", "close", "change"}}

    OI is polled, not streamed, and it moves every few seconds - weight 1 per call.
    A bar where OI rose while price stalled is absorption; where OI fell, it was closing.
    """
    by_minute = {}
    for ms, value in samples:
        minute = (ms // 60000) * 60000
        bucket = by_minute.setdefault(minute, {"open": value, "close": value})
        bucket["close"] = value

    for bucket in by_minute.values():
        bucket["change"] = round(bucket["close"] - bucket["open"], 2)
    return by_minute


def book_at_level(book, level, buckets=3, bucket_size=BUCKET):
    """
    Notional resting within `buckets` rows above and below a level.

    This is the difference between a level being defended and a level being left:
    bids stacked under it means somebody is there; bids pulled means nobody is.
    """
    low = level - buckets * bucket_size
    high = level + buckets * bucket_size

    bids = sum(float(price) * float(qty) for price, qty in book["bids"] if low <= float(price) <= level)
    asks = sum(float(price) * float(qty) for price, qty in book["asks"] if level <= float(price) <= high)
    total = bids + asks

    return {
        "bids": round(bids, 2),
        "asks": round(asks, 2),
        "imbalance": round((bids - asks) / total, 3) if total else 0.0,
    }


def absorption_score(bar, event):
    """
    0-5, from what the bar itself proves. No opinion, no forecast.

        1  the row is heavy        at least 3x the bar's median row
        2  it is the heaviest      the POC of the bar sits on this price
        3  the bar rejected it     close is away by more than the bucket
        4  the POC sits in the wick  price fought there and lost, then closed away
        5  the next bar held       price did not accept through the absorbed bar
    """
    score = 0
    sizes = sorted((row["buy"] + row["sell"]) for row in bar["rows"].values())
    median = sizes[len(sizes) // 2] if sizes else 0

    if median and event["size"] >= median * 3:
        score += 1
    if bar["poc"] is not None and abs(bar["poc"] - event["price"]) < 1e-9:
        score += 1
    if abs(bar["close"] - event["price"]) > BUCKET:
        score += 1

    if bar["high"] > bar["low"]:
        position = (event["price"] - bar["low"]) / (bar["high"] - bar["low"])
        in_wick = position < 0.15 or position > 0.85
        if in_wick:
            score += 1

    return score


def verdict(absorbed, after):
    """HELD if the next bar did not accept through the level, EATEN if it did."""
    if after is None:
        return "pending"
    if after["close"] > absorbed["high"]:
        return "held-up"
    if after["close"] < absorbed["low"]:
        return "held-down"
    return "inside"


if __name__ == "__main__":
    import sys

    path = sys.argv[1]
    started = time.time()
    bars = bars_from_trades(read_csv(path))
    events = sum(len(absorption_candidates(bar)) for bar in bars)
    print(f"bars {len(bars)}  absorptions {events}  in {time.time() - started:.1f}s")
    for bar in bars[-3:]:
        print(f"  {time.strftime('%H:%M', time.gmtime(bar['t'] / 1000))} "
              f"o{bar['open']} h{bar['high']} l{bar['low']} c{bar['close']} "
              f"delta {bar['delta']:+.2f} poc {bar['poc']} {bar['pocSide']}")
