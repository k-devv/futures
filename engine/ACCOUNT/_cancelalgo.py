import json
import account
import trade

rows = account.algo_orders("BNBUSDT")
print("algo before", len(rows))
for row in rows:
    algo_id = row.get("algoId")
    try:
        trade.cancel_algo(algo_id)
        print("cancelled", algo_id)
    except Exception as error:
        print("cancel failed", algo_id, type(error).__name__, str(error)[:150])

print("algo after", len(account.algo_orders("BNBUSDT")))
print("positions", account.positions("BNBUSDT"))