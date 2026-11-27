import json, time
import account
import trade

print("balance", account.usdt())

try:
    entry_order = trade.market_entry("BUY", 0.19)
    print("entry order", entry_order.get("status"), entry_order.get("avgPrice"), entry_order.get("executedQty"))
except Exception as error:
    print("ENTRY ERROR", type(error).__name__, str(error)[:200])
    raise SystemExit

time.sleep(1)
positions = account.positions("BNBUSDT")
print("positions", positions)
if not positions:
    raise SystemExit

fill = positions[0]["entry"]
stop = round(fill - 2.0, 2)
target = round(fill + 4.0, 2)
print("fill", fill, "stop", stop, "target", target)

try:
    protection = trade.protect("BUY", positions[0]["amount"], stop, target)
    print("stop id", protection["stop"].get("algoId"), "target id", protection["target"].get("algoId"))
except Exception as error:
    print("PROTECT ERROR", type(error).__name__, str(error)[:300])
    trade.close_position("SELL", positions[0]["amount"])
    print("position closed for safety")

print("positions after", account.positions("BNBUSDT"))
print("algo orders", len(account.algo_orders("BNBUSDT")))