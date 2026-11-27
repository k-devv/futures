import json, time
import account
import trade

positions = account.positions("BNBUSDT")
print("before", json.dumps(positions))
if not positions:
    print("nothing open")
    raise SystemExit

row = positions[0]
qty = abs(row["amount"])
side = "SELL" if row["side"] == "long" else "BUY"

order = trade.close_position(side, qty)
print("close order", order.get("status"), order.get("avgPrice"), order.get("executedQty"))

time.sleep(2)
print("after", json.dumps(account.positions("BNBUSDT")))
print("open orders", len(account.open_orders("BNBUSDT")), "algo", len(account.algo_orders("BNBUSDT")))
print("wallet", account.usdt())