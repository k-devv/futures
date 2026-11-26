"""
================================================================================
 binance/endpoint/api.py  -  the only file that talks to Binance
================================================================================
 WHAT   : Two bases, one call(). Public market data goes to the production host
          (the demo host does not serve /futures/data/*), everything private and
          everything that moves money goes to the demo host from keys.json.
 WHY    : Every external detail - signing, clock offset, lot steps, endpoints -
          lives here, so no other file knows how Binance works.
 WHERE  : Futures/binance/endpoint  (keys in Futures/binance/keys, gitignored)
 SCALE  : Add a name to MARKET or PRIVATE. Add a wrapper only when a caller
          needs one.
================================================================================

    python binance/endpoint/api.py account
    python binance/endpoint/api.py taker_ratio 5m
"""

import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))          # binance/endpoint
KEYS_DIR = os.path.join(os.path.dirname(HERE), "keys")     # binance/keys

with open(os.path.join(KEYS_DIR, "keys.json"), encoding="utf-8") as handle:
    KEYS = json.load(handle)

SYMBOL = KEYS.get("symbol", "BNBUSDT")
TRADE_BASE = KEYS.get("baseUrl", "https://demo-fapi.binance.com").rstrip("/")
MARKET_BASE = "https://fapi.binance.com"                   # public data lives here, always
API_KEY = KEYS["apiKey"]
API_SECRET = KEYS["apiSecret"]

# ------------------------------------------------------------------ endpoints
# public: no signature, production host
MARKET = {
    "server_time":        "/fapi/v1/time",
    "exchange_info":      "/fapi/v1/exchangeInfo",
    "klines":             "/fapi/v1/klines",
    "agg_trades":         "/fapi/v1/aggTrades",       # the tape, up to 1000 per call
    "trades":             "/fapi/v1/trades",          # recent trades, has isRPITrade
    "depth":              "/fapi/v1/depth",           # order book snapshot
    "book_ticker":        "/fapi/v1/ticker/bookTicker",
    "premium_index":      "/fapi/v1/premiumIndex",    # mark, index, funding
    "funding_rate":       "/fapi/v1/fundingRate",
    "open_interest":      "/fapi/v1/openInterest",    # right now
    "open_interest_hist": "/futures/data/openInterestHist",     # 5m..1d, 30 days
    "taker_ratio":        "/futures/data/takerlongshortRatio",  # official buy/sell volume
    "long_short":         "/futures/data/globalLongShortAccountRatio",
    "top_long_short":     "/futures/data/topLongShortPositionRatio",
    "basis":              "/futures/data/basis",
}

# private: signed, demo host from keys.json
PRIVATE = {
    "account":        "/fapi/v3/account",
    "account_v2":     "/fapi/v2/account",
    "positions":      "/fapi/v2/positionRisk",
    "ud_trades":      "/fapi/v1/userTrades",
    "income":         "/fapi/v1/income",
    "order":          "/fapi/v1/order",
    "query_order":    "/fapi/v1/order",
    "cancel_order":   "/fapi/v1/order",
    "algo_order":     "/fapi/v1/algoOrder",
    "open_algo":      "/fapi/v1/openAlgoOrders",
    "cancel_algo":    "/fapi/v1/algoOrder",
    "historical":     "/fapi/v1/historicalTrades",
    "leverage":       "/fapi/v1/leverage",
    "margin_type":    "/fapi/v1/marginType",
    "commission":     "/fapi/v1/commissionRate",
}

# ------------------------------------------------------------------ state
_clock_offset = 0        # ms; Binance time minus ours, fixed once at start
_weight_1m = 0           # the last X-MBX-USED-WEIGHT-1M Binance reported
_filters = {}            # symbol -> {qty_step, price_tick, min_qty}
_filters_at = 0


# ------------------------------------------------------------------ plumbing
def _now():
    """Binance's clock, not ours. A request signed with a fast local clock is rejected."""
    return int(time.time() * 1000) + _clock_offset


def sync_clock():
    """Measure the offset once. Cheap, and it removes a whole class of -1021 errors."""
    global _clock_offset
    sent = int(time.time() * 1000)
    with urllib.request.urlopen(MARKET_BASE + MARKET["server_time"], timeout=10) as response:
        theirs = json.loads(response.read())["serverTime"]
    _clock_offset = theirs - sent
    return _clock_offset


def filters():
    """Lot step and price tick for our symbol, cached for six hours."""
    global _filters, _filters_at
    if _filters and time.time() - _filters_at < 6 * 3600:
        return _filters

    with urllib.request.urlopen(MARKET_BASE + MARKET["exchange_info"], timeout=15) as response:
        payload = json.loads(response.read())

    for item in payload.get("symbols", []):
        if item.get("symbol") != SYMBOL:
            continue
        steps = {"qty_step": 0.001, "price_tick": 0.01, "min_qty": 0.001}
        for rule in item.get("filters", []):
            if rule.get("filterType") == "LOT_SIZE":
                steps["qty_step"] = float(rule["stepSize"])
                steps["min_qty"] = float(rule["minQty"])
            if rule.get("filterType") == "PRICE_FILTER":
                steps["price_tick"] = float(rule["tickSize"])
        _filters = steps
        _filters_at = time.time()
        break

    return _filters


def _request(base, path, params, method, signed):
    query_params = dict(params or {})
    if signed:
        query_params["timestamp"] = _now()
        query_params["recvWindow"] = 5000

    query = urllib.parse.urlencode(query_params)
    if signed:
        signature = hmac.new(API_SECRET.encode(), query.encode(), hashlib.sha256).hexdigest()
        url = f"{base}{path}?{query}&signature={signature}"
    else:
        url = f"{base}{path}?{query}" if query else f"{base}{path}"

    headers = {"User-Agent": "futures/0.1"}
    if signed:
        headers["X-MBX-APIKEY"] = API_KEY

    request = urllib.request.Request(url, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            global _weight_1m
            _weight_1m = int(response.headers.get("X-MBX-USED-WEIGHT-1M") or 0)
            body = response.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode()[:200]
        raise RuntimeError(f"{method} {path} -> HTTP {error.code} {detail}") from None
    except urllib.error.URLError as error:
        raise RuntimeError(f"{method} {path} -> {error.reason}") from None


def call(name, params=None, method="GET"):
    """Call a named endpoint from either table."""
    if name in MARKET:
        return _request(MARKET_BASE, MARKET[name], params, method, signed=False)
    if name in PRIVATE:
        return _request(TRADE_BASE, PRIVATE[name], params, method, signed=True)

    # an explicit path is allowed, and is treated as private
    return _request(TRADE_BASE, name, params, method, signed=True)


def snapshot():
    """
    One screen of everything that matters at this second, in the order we read it:
    price, open interest, taker ratio, book imbalance, and the retail share of the tape.
    """
    mark = call("premium_index", {"symbol": SYMBOL})
    oi_now = call("open_interest", {"symbol": SYMBOL})
    oi_hist = call("open_interest_hist", {"symbol": SYMBOL, "period": "5m", "limit": 2})[-1]
    taker = call("taker_ratio", {"symbol": SYMBOL, "period": "5m", "limit": 1})[-1]
    book = call("depth", {"symbol": SYMBOL, "limit": 20})
    tape = call("trades", {"symbol": SYMBOL, "limit": 200})

    bids = sum(float(price) * float(qty) for price, qty in book["bids"])
    asks = sum(float(price) * float(qty) for price, qty in book["asks"])
    # /trades marks RPI per trade; aggTrades gives nq instead. Use whichever is present.
    retail = sum(float(t["qty"]) for t in tape if t.get("isRPITrade"))
    volume = sum(float(t["qty"]) for t in tape)

    return {
        "price": float(mark["markPrice"]),
        "funding": float(mark.get("lastFundingRate", 0)),
        "open_interest": float(oi_now["openInterest"]),
        "oi_5m_ago": float(oi_hist["sumOpenInterest"]),
        "oi_change_5m": round(float(oi_now["openInterest"]) - float(oi_hist["sumOpenInterest"]), 2),
        "taker_ratio_5m": float(taker["buySellRatio"]),
        "book_imbalance": round((bids - asks) / (bids + asks), 3),
        "tape_retail_share": round(retail / volume, 3) if volume else 0,
        "weight_1m": _weight_1m,
    }


if __name__ == "__main__":
    import sys

    sync_clock()
    what = sys.argv[1] if len(sys.argv) > 1 else "account"
    arg = sys.argv[2] if len(sys.argv) > 2 else None

    if what == "snapshot":
        print(json.dumps(snapshot(), indent=2))
        raise SystemExit(0)

    if what in ("taker_ratio", "open_interest_hist", "long_short", "top_long_short", "basis"):
        params = {"symbol": SYMBOL, "period": arg or "5m", "limit": 3}
        if what == "basis":
            params = {"pair": SYMBOL, "contractType": "PERPETUAL", "period": arg or "5m", "limit": 3}
    elif what in ("positions", "ud_trades", "open_algo", "funding_rate",
                  "open_interest", "depth", "klines", "trades", "agg_trades"):
        params = {"symbol": SYMBOL, "limit": 3}
    else:
        params = {"symbol": SYMBOL} if what in ("order", "query_order", "algo_order") else None

    print(json.dumps(call(what, params), indent=2)[:1200])
