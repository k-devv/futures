import json
import account
import trade

qty = 0.19
stop_price = 551.66
target_price = 557.66

try:
    s = trade.stop("SELL", qty, stop_price)
    print("STOP", json.dumps(s)[:300])
except Exception as error:
    print("STOP FAILED", type(error).__name__, str(error)[:200])

try:
    t = trade.take_profit("SELL", qty, target_price)
    print("TARGET", json.dumps(t)[:300])
except Exception as error:
    print("TARGET FAILED", type(error).__name__, str(error)[:200])

print("algo orders now:")
for row in account.algo_orders("BNBUSDT"):
    print(" ", json.dumps(row)[:250])