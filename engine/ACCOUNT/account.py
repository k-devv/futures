"""
================================================================================
 ACCOUNT - account.py  -  reading the real Binance futures account
================================================================================
 WHAT   : Signed reads of the live USDⓈ-M futures account: balance, positions,
          open orders, leverage, margin type, income. Nothing here places an
          order - that lives in trade.py.

 WHY    : One place that knows how to sign a request, which host to talk to, and
          what shape each answer has. If something is wrong with the account,
          this file answers it without touching the trading code.

 HOST   : https://fapi.binance.com        (live). The demo host is
          https://demo-fapi.binance.com and the keys are different - never mix
          them: a demo key on the live host returns -2015.

 KEYS   : binance/keys/live.json   { "key": "...", "secret": "..." }

 COST   : every call is weight 1-5. The page polls /api/balance every 15 s and
          the server caches it, so this file is not called in a hot loop.
================================================================================
"""

import hashlib
import hmac
import json
import os
import time
import urllib.parse
import urllib.request

BASE = "https://fapi.binance.com"

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KEYS = os.path.join(ROOT, "binance", "keys", "live.json")


# ------------------------------------------------------------------ primitives
def load_keys():
    """
    The live key pair.

    Output  {"key": str, "secret": str}
    Raises  FileNotFoundError when the file is missing - better to fail loudly
            than to trade with no credentials.
    """
    with open(KEYS, encoding="utf-8") as handle:
        keys = json.load(handle)

    if not keys.get("key") or not keys.get("secret"):
        raise ValueError("live.json is missing key or secret")

    return keys


def signed(path, params=None, method="GET"):
    """
    One signed request to the live futures API.

    Input   path ("/fapi/v2/balance"), query params, HTTP method
    Output  decoded JSON (dict or list)
    Raises  RuntimeError carrying Binance's own error code and message

    Signing rule: HMAC-SHA256 of the QUERY STRING, with the API key in a header.
    Every call needs a timestamp inside recvWindow (5 s here).
    """
    keys = load_keys()
    query_params = dict(params or {})
    query_params["timestamp"] = int(time.time() * 1000)
    query_params.setdefault("recvWindow", 5000)

    query = urllib.parse.urlencode(query_params)
    signature = hmac.new(keys["secret"].encode(), query.encode(), hashlib.sha256).hexdigest()

    url = f"{BASE}{path}?{query}&signature={signature}"
    request = urllib.request.Request(url, method=method, headers={"X-MBX-APIKEY": keys["key"]})

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        body = error.read().decode(errors="ignore")
        raise RuntimeError(f"binance {error.code}: {body}") from None


# ------------------------------------------------------------------ the account
def balance():
    """
    Per-asset futures wallet.

    Output  [{"asset": "USDT", "balance": float, "available": float}, ...]
            only assets with a non-zero balance
    Cost    weight 5
    """
    rows = signed("/fapi/v2/balance")

    result = []
    for row in rows:
        amount = float(row["balance"])
        if amount:
            result.append({
                "asset": row["asset"],
                "balance": amount,
                "available": float(row["availableBalance"]),
            })
    return result


def usdt():
    """
    Just the USDT wallet, which is the only one this system trades.

    Output  {"wallet": float, "available": float}
    """
    for row in balance():
        if row["asset"] == "USDT":
            return {"wallet": row["balance"], "available": row["available"]}
    return {"wallet": 0.0, "available": 0.0}


def account():
    """
    The full account object: balances, positions, permissions.

    Output  dict as Binance returns it
    Cost    weight 5
    """
    return signed("/fapi/v2/account")


def positions(symbol=None):
    """
    Open positions only.

    Input   symbol to filter (optional)
    Output  [{"symbol", "amount", "entry", "unrealized", "leverage", "side"}]
            amount is signed: positive long, negative short
    """
    rows = account().get("positions", [])

    result = []
    for row in rows:
        amount = float(row["positionAmt"])
        if amount == 0 or (symbol and row["symbol"] != symbol):
            continue

        result.append({
            "symbol": row["symbol"],
            "amount": amount,
            "entry": float(row["entryPrice"]),
            # /fapi/v2/account spells it unrealizedProfit, positionRisk spells it
            # unRealizedProfit - accept either, never KeyError on a live position
            "unrealized": float(row.get("unRealizedProfit", row.get("unrealizedProfit", 0))),
            "leverage": int(row["leverage"]),
            "side": "long" if amount > 0 else "short",
        })
    return result


def open_orders(symbol=None):
    """
    Plain open orders (limit, market, stop-market). Does NOT include the
    conditional/algo orders - those live in algo_orders().
    """
    params = {"symbol": symbol} if symbol else {}
    return signed("/fapi/v1/openOrders", params)


def algo_orders(symbol=None):
    """
    Conditional orders (the ones placed through /fapi/v1/algoOrder with
    algoType=CONDITIONAL). Binance keeps them in a separate book from 2025 on,
    so a stop you cannot find in open_orders() is almost certainly here.
    """
    params = {"symbol": symbol} if symbol else {}
    return signed("/fapi/v1/openAlgoOrders", params)


def leverage(symbol):
    """
    Current leverage for a symbol.

    Docs: /fapi/v2/positionRisk carries the live `leverage` field per position.
    /fapi/v1/leverageBracket is NOT the setting - it lists the maximum leverage
    allowed at each notional bracket, which is a different number.
    """
    rows = signed("/fapi/v2/positionRisk", {"symbol": symbol})
    for row in rows:
        if row.get("symbol") == symbol:
            return int(row["leverage"])

    # when the account is flat Binance may return no row for the symbol at all.
    # the setting still exists; ask without the filter and look for it.
    for row in signed("/fapi/v2/positionRisk"):
        if row.get("symbol") == symbol:
            return int(row["leverage"])
    return None


def max_leverage(symbol):
    """The highest leverage the exchange will allow in the smallest bracket."""
    rows = signed("/fapi/v1/leverageBracket", {"symbol": symbol})
    for row in rows:
        if row.get("symbol") == symbol and row.get("brackets"):
            return int(row["brackets"][0]["initialLeverage"])
    return None


def position_risk(symbol):
    """Raw position risk row: entry, leverage, liquidation, margin type."""
    rows = signed("/fapi/v2/positionRisk", {"symbol": symbol})
    return rows[0] if rows else None


def set_leverage(symbol, value):
    """
    Set leverage. Kept low on purpose: leverage changes the liquidation price,
    not the risk - the stop does that.
    """
    return signed("/fapi/v1/leverage", {"symbol": symbol, "leverage": int(value)}, method="POST")


def margin_type(symbol):
    """'cross' or 'isolated' - from the v2 position risk endpoint."""
    rows = signed("/fapi/v2/positionRisk", {"symbol": symbol})
    if rows:
        return rows[0]["marginType"]

    for row in signed("/fapi/v2/positionRisk"):
        if row.get("symbol") == symbol:
            return row["marginType"]
    return None


def income(limit=50):
    """
    Realised income rows: funding, commission, realised PnL.

    Output  [{"time", "type", "asset", "amount"}, ...] newest first
    """
    rows = signed("/fapi/v1/income", {"limit": limit})
    return [
        {
            "time": int(row["time"]),
            "type": row["incomeType"],
            "asset": row["asset"],
            "amount": float(row["income"]),
        }
        for row in rows
    ]


def summary(symbol="BNBUSDT"):
    """
    One compact read for the header and the log.

    Output  {"usdt": {...}, "positions": [...], "orders": int, "algo": int}
    """
    wallet = usdt()
    open_now = positions()
    return {
        "usdt": wallet,
        "positions": open_now,
        "orders": len(open_orders(symbol)),
        "algo": len(algo_orders(symbol)),
    }


if __name__ == "__main__":
    print(json.dumps(summary(), indent=2))
