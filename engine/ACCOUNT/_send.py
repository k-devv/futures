import json, urllib.request
import account
import trade

book = json.loads(urllib.request.urlopen("https://fapi.binance.com/fapi/v1/ticker/bookTicker?symbol=BNBUSDT", timeout=10).read())
bid = float(book["bidPrice"])
entry = round(bid - 0.01, 2)
stop = round(entry - 2.0, 2)
target = round(entry + 4.0, 2)
print("bid", bid, "entry", entry, "stop", stop, "target", target)

try:
    result = trade.open_trade("BUY", 0.19, entry, stop, target, wait_seconds=30)
    print(json.dumps(result, indent=2, default=str)[:1500] if result else "NOT FILLED - order cancelled")
except Exception as error:
    print("ERROR", type(error).__name__, str(error)[:300])

print("positions", account.positions("BNBUSDT"))
print("open orders", len(account.open_orders("BNBUSDT")), "algo", len(account.algo_orders("BNBUSDT")))