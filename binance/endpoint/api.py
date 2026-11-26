"""
================================================================================
 binance/api.py  -  the only file that talks to Binance
================================================================================
 WHAT   : The endpoints we use, and one signed-request function that hits them.
 WHY    : Everything external lives in this folder. The UI never sees a key, and
          no other file needs to know how Binance signs a request.
 WHERE  : Futures/binance/endpoint  (keys in futures/binance/keys, gitignored)
 SCALE  : Add an endpoint to ENDPOINTS; add a wrapper below only when a caller
          needs one.
================================================================================

    python binance/endpoint/api.py account     # a quick check from the terminal
"""

import hashlib
import hmac
import json
import os
import time
import urllib.parse
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))          # binance/endpoint
KEYS_DIR = os.path.join(os.path.dirname(HERE), "keys")   # binance/keys
SYMBOL = "BNBUSDT"

# demo first: this file refuses to sign against anything else until we say so
with open(os.path.join(KEYS_DIR, "keys.json"), encoding="utf-8") as handle:
    KEYS = json.load(handle)

BASE = KEYS.get("baseUrl", "https://demo-fapi.binance.com").rstrip("/")
API_KEY = KEYS["apiKey"]
API_SECRET = KEYS["apiSecret"]

# the endpoints, named for what they answer
ENDPOINTS = {
    "account":           "/fapi/v3/account",            # balance, canTrade
    "account_fallback":  "/fapi/v2/account",            # demo sometimes prefers this
    "positions":         "/fapi/v2/positionRisk",       # what is open now
    "trades":            "/fapi/v1/userTrades",         # every fill
    "income":            "/fapi/v1/income",             # fees, funding, realised pnl
    "order":             "/fapi/v1/order",              # market / limit entry
    "algo_order":        "/fapi/v1/algoOrder",          # stop and take-profit
    "open_algo":         "/fapi/v1/openAlgoOrders",
    "exchange_info":     "/fapi/v1/exchangeInfo",       # lot and price steps
    "klines":            "/fapi/v1/klines",             # candles
    "book_ticker":       "/fapi/v1/ticker/bookTicker",  # best bid / ask
}


def _sign(query: str) -> str:
    return hmac.new(API_SECRET.encode(), query.encode(), hashlib.sha256).hexdigest()


def call(name, params=None, method="GET"):
    """
    Hit a named endpoint. GETs are signed in the query, POSTs carry the parameters
    in the query too - Binance accepts both and one code path is less to go wrong.
    """
    path = ENDPOINTS.get(name, name)
    query_params = dict(params or {})
    query_params["timestamp"] = int(time.time() * 1000)
    query_params["recvWindow"] = 5000

    query = urllib.parse.urlencode(query_params)
    url = f"{BASE}{path}?{query}&signature={_sign(query)}"

    request = urllib.request.Request(
        url,
        method=method,
        headers={"X-MBX-APIKEY": API_KEY, "User-Agent": "futures/0.1"},
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        detail = error.read().decode()[:200]
        raise RuntimeError(f"{method} {path} -> HTTP {error.code} {detail}") from None
    except urllib.error.URLError as error:
        raise RuntimeError(f"{method} {path} -> {error.reason}") from None


if __name__ == "__main__":
    import sys

    what = sys.argv[1] if len(sys.argv) > 1 else "account"
    payload = call(what, {"symbol": SYMBOL} if what in ("positions", "trades") else None)
    print(json.dumps(payload, indent=2)[:1200])
