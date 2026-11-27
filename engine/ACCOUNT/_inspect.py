import json
import account

acct = account.account()
print("canTrade", acct.get("canTrade"), "wallet", acct.get("totalWalletBalance"))
open_rows = [p for p in acct.get("positions", []) if float(p.get("positionAmt", 0)) != 0]
print("open positions:", len(open_rows))
for row in open_rows:
    print(json.dumps({k: row[k] for k in list(row)[:12]}, indent=2)[:500])

print("openOrders", json.dumps(account.open_orders("BNBUSDT"))[:400])
print("algo", json.dumps(account.algo_orders("BNBUSDT"))[:400])
print("risk", json.dumps(account.position_risk("BNBUSDT"))[:400])