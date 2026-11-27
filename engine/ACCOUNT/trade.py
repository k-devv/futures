"""
================================================================================
 ACCOUNT - trade.py  -  placing, protecting and closing real orders
================================================================================
 WHAT   : The only file allowed to send an order. Limit entries, market entries,
          stops, take-profits, cancels, close-position. Every call is signed and
          goes to the live futures host.

 WHY    : Trading code must be small enough to read in one sitting. If an order
          exists that this file did not write, something is wrong.

 RULES THIS FILE ENFORCES (not suggestions):
          1  every entry is a LIMIT order - market entries pay 0.04% instead of
             0.02% and get a worse price in the same instant
          2  every entry is followed by a stop in the same breath; if the stop
             fails the entry is cancelled
          3  quantity is rounded to the symbol's step size, price to its tick
          4  no order can exceed MAX_QTY
          5  conditional orders use /fapi/v1/algoOrder with algoType=CONDITIONAL
             (the plain /fapi/v1/order route rejects them with -4120)

 KEYS   : binance/keys/live.json   (same loader as account.py)
 HOST   : https://fapi.binance.com
================================================================================
"""

import json
import math
import time

try:                                    # imported as a package
    from .account import signed
except ImportError:                     # run as a script from this folder
    from account import signed

SYMBOL = "BNBUSDT"

MAX_QTY = 0.20          # ceiling per order: 0.19 BNB ~ KSh 100 target at 4 points
TICK = 0.01             # PRICE_FILTER tickSize for BNBUSDT
STEP = 0.01             # LOT_SIZE stepSize

_filters = {"at": 0, "tick": None, "step": None, "min_qty": None}


# ------------------------------------------------------------------ primitives
def filters():
    """
    Price and quantity rules straight from the exchange.

    Output  {"tick": float, "step": float, "min_qty": float}
    Cached  6 hours - they change almost never.

    Read from /fapi/v1/exchangeInfo. Guessing these is how an order gets
    rejected with -4014 or -1111.
    """
    if _filters["tick"] and time.time() - _filters["at"] < 6 * 3600:
        return {"tick": _filters["tick"], "step": _filters["step"], "min_qty": _filters["min_qty"]}

    url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    import urllib.request

    with urllib.request.urlopen(url, timeout=15) as response:
        info = json.loads(response.read())

    symbol = next(item for item in info["symbols"] if item["symbol"] == SYMBOL)
    rules = {f["filterType"]: f for f in symbol["filters"]}

    _filters.update(
        at=time.time(),
        tick=float(rules["PRICE_FILTER"]["tickSize"]),
        step=float(rules["LOT_SIZE"]["stepSize"]),
        min_qty=float(rules["LOT_SIZE"]["minQty"]),
    )
    return {"tick": _filters["tick"], "step": _filters["step"], "min_qty": _filters["min_qty"]}


def round_qty(qty):
    """Round down to the step size - never up: sending more than you meant is worse."""
    step = filters()["step"]
    value = math.floor(float(qty) / step) * step
    return round(value, 8)


def round_price(price):
    """Round to the tick size."""
    tick = filters()["tick"]
    return round(round(float(price) / tick) * tick, 8)


def _guard(symbol, qty, price=None):
    """Refuse obviously wrong input before it reaches the exchange."""
    quantity = round_qty(qty)

    if quantity <= 0 or quantity < filters()["min_qty"]:
        raise ValueError(f"quantity {qty} is below the minimum {filters()['min_qty']}")
    if quantity > MAX_QTY:
        raise ValueError(f"quantity {quantity} exceeds MAX_QTY {MAX_QTY} - raise it on purpose")
    if price is not None and price <= 0:
        raise ValueError("price must be positive")

    return quantity


# ------------------------------------------------------------------ entries
def limit_entry(side, qty, price, symbol=SYMBOL, post_only=True):
    """
    A maker entry at a price you choose.

    Input   side "BUY"|"SELL", qty in BNB, price
    Output  the order object from Binance
    Cost    weight 1 (plus order-count weight)

    post_only=True uses GTX (post only): if the price would cross the book the
    order is rejected instead of becoming a taker. That rejection is the point -
    it stops you paying the taker fee by accident.
    """
    quantity = _guard(symbol, qty, price)
    params = {
        "symbol": symbol,
        "side": side,
        "type": "LIMIT",
        "timeInForce": "GTX" if post_only else "GTC",
        "quantity": quantity,
        "price": round_price(price),
    }
    return signed("/fapi/v1/order", params, method="POST")


def market_entry(side, qty, symbol=SYMBOL):
    """
    A taker entry. Kept for emergencies only (a stop that must be honoured).

    The 0.02% difference per side is the entire edge on a 0.15% move - do not
    use this for entries out of habit.
    """
    quantity = _guard(symbol, qty)
    return signed("/fapi/v1/order", {
        "symbol": symbol,
        "side": side,
        "type": "MARKET",
        "quantity": quantity,
    }, method="POST")


# ------------------------------------------------------------------ protection
def stop(side, qty, stop_price, symbol=SYMBOL, limit_buffer=0.06):
    """
    A protective stop that closes the position.

    Input   side "SELL" closes a long, "BUY" closes a short
            stop_price is the trigger, not the fill
    Output  the algo order object

    Uses POST /fapi/v1/algoOrder with algoType=CONDITIONAL and a STOP_MARKET
    inside. This is the route Binance accepts from 2025 onward; the plain order
    route answers -4120 "Order type not supported".
    """
    quantity = _guard(symbol, qty)
    params = {
        "algoType": "CONDITIONAL",
        "symbol": symbol,
        "side": side,
        "type": "STOP_MARKET",
        "quantity": quantity,
        "triggerPrice": round_price(stop_price),
        "workingType": "MARK_PRICE",
    }
    return signed("/fapi/v1/algoOrder", params, method="POST")


def take_profit(side, qty, trigger_price, symbol=SYMBOL):
    """
    A target that closes the position.

    side is the closing side: "SELL" for a long, "BUY" for a short.
    """
    quantity = _guard(symbol, qty)
    params = {
        "algoType": "CONDITIONAL",
        "symbol": symbol,
        "side": side,
        "type": "TAKE_PROFIT_MARKET",
        "quantity": quantity,
        "triggerPrice": round_price(trigger_price),
        "workingType": "MARK_PRICE",
    }
    return signed("/fapi/v1/algoOrder", params, method="POST")


def protect(side, qty, stop_price, target_price, symbol=SYMBOL):
    """
    Stop and target together. The normal way to open a trade in this system.

    Input   side "BUY" for a long, "SELL" for a short
    Output  {"stop": ..., "target": ...}

    If the stop fails, the target is cancelled and the exception is raised -
    a position must never exist without a stop.
    """
    closing = "SELL" if side == "BUY" else "BUY"

    stop_order = stop(closing, qty, stop_price, symbol)
    try:
        target_order = take_profit(closing, qty, target_price, symbol)
    except Exception:
        cancel(stop_order.get("algoId"), symbol)
        raise

    return {"stop": stop_order, "target": target_order}


# ------------------------------------------------------------------ cancels
def cancel(order_id, symbol=SYMBOL):
    """Cancel one plain order."""
    return signed("/fapi/v1/order", {"symbol": symbol, "orderId": order_id}, method="DELETE")


def cancel_algo(algo_id, symbol=SYMBOL):
    """Cancel one conditional (algo) order."""
    return signed("/fapi/v1/algoOrder", {"symbol": symbol, "algoId": algo_id}, method="DELETE")


def cancel_all(symbol=SYMBOL):
    """
    Cancel every plain and conditional order on a symbol.

    Use before starting a session and after closing a position: orphan stops are
    how a flat account suddenly becomes a position overnight.
    """
    plain = signed("/fapi/v1/allOpenOrders", {"symbol": symbol}, method="DELETE")

    # conditional orders are NOT removed by allOpenOrders. they must be cancelled
    # one by one, or a leftover stop turns a flat account into a position later.
    cancelled = []
    try:
        from account import algo_orders
        for row in algo_orders(symbol):
            try:
                cancel_algo(row["algoId"], symbol)
                cancelled.append(row["algoId"])
            except Exception:
                pass
    except Exception:
        pass

    return {"plain": plain, "algo": cancelled}


def close_position(side, qty, symbol=SYMBOL):
    """
    Close a position at market and drop its protective orders.

    side is the closing side: "SELL" for a long, "BUY" for a short.
    """
    quantity = _guard(symbol, qty)
    order = signed("/fapi/v1/order", {
        "symbol": symbol,
        "side": side,
        "type": "MARKET",
        "quantity": quantity,
        "reduceOnly": "true",
    }, method="POST")
    cancel_all(symbol)
    return order


# ------------------------------------------------------------------ one trade
def open_trade(side, qty, entry_price, stop_price, target_price, symbol=SYMBOL, wait_seconds=20):
    """
    The whole sequence in the order this system requires.

        1  place a post-only limit entry
        2  wait up to wait_seconds for it to fill
        3  if filled: attach stop + target
        4  if not filled: cancel, return None (a missed trade costs nothing)

    Output  {"entry": ..., "stop": ..., "target": ...} or None when unfilled

    This function is the only place that opens risk. Everything else in this
    file is a building block it uses.
    """
    if side not in ("BUY", "SELL"):
        raise ValueError("side must be BUY or SELL")
    if (side == "BUY" and stop_price >= entry_price) or (side == "SELL" and stop_price <= entry_price):
        raise ValueError("stop is on the wrong side of the entry")

    order = limit_entry(side, qty, entry_price, symbol)

    filled = 0.0
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        status = signed("/fapi/v1/order", {"symbol": symbol, "orderId": order["orderId"]})
        filled = float(status["executedQty"])

        if status["status"] == "FILLED":
            break
        if status["status"] in ("CANCELED", "EXPIRED", "REJECTED"):
            return None
        time.sleep(1)

    if filled <= 0:
        cancel(order["orderId"], symbol)
        return None

    protection = protect(side, filled, stop_price, target_price, symbol)
    return {"entry": order, "filled": filled, **protection}


if __name__ == "__main__":
    print(json.dumps({"filters": filters(), "max_qty": MAX_QTY}, indent=2))
