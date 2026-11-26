"""
================================================================================
 engine/footprint/tape.py  -  the live tape, and nothing else
================================================================================
 WHAT   : One websocket to Binance's trade stream. Hands every fill to a callback
          as (price, qty, is_buyer_maker, ms). Reconnects by itself when the
          socket drops, which it will - Binance closes connections on purpose.
 WHY    : This is the only live source of truth in the system. Everything the
          footprint shows comes from here, so it has to be boring and patient.
 WHERE  : Futures/engine/footprint
 SCALE  : One symbol, one stream. Add a second stream only if the footprint
          genuinely needs it.

    python engine/footprint/tape.py        live, prints a line per second
"""

import asyncio
import json
import sys
import time

import websockets

SYMBOL = "BNBUSDT"
URL = f"wss://fstream.binance.com/ws/{SYMBOL.lower()}@trade"

PING_SECONDS = 20        # keep the connection honest
BACKOFF = [1, 2, 5, 10, 30]   # reconnect delays, then hold at the last one


def parse(message):
    """
    Binance trade payload -> our tuple, or None if it is a control message.

        {"e":"trade","T":1795726073217,"p":"556.460","q":"0.46","m":true}
    """
    payload = json.loads(message)
    if payload.get("e") != "trade":
        return None
    return float(payload["p"]), float(payload["q"]), bool(payload["m"]), int(payload["T"])


async def stream(on_trade, symbol=SYMBOL, url=None, quiet=False):
    """
    Run forever: connect, hand trades to on_trade, reconnect when it breaks.

    on_trade(price, qty, is_buyer_maker, ms) is called for every fill.
    """
    target = url or f"wss://fstream.binance.com/ws/{symbol.lower()}@trade"
    attempt = 0

    while True:
        try:
            async with websockets.connect(target, ping_interval=PING_SECONDS,
                                          ping_timeout=10, close_timeout=2) as socket:
                attempt = 0
                if not quiet:
                    print(f"tape connected  {target}", flush=True)

                async for message in socket:
                    trade = parse(message)
                    if trade:
                        on_trade(*trade)

        except asyncio.CancelledError:
            raise
        except Exception as error:
            delay = BACKOFF[min(attempt, len(BACKOFF) - 1)]
            if not quiet:
                print(f"tape dropped    {type(error).__name__} - reconnecting in {delay}s", flush=True)
            attempt += 1
            await asyncio.sleep(delay)


if __name__ == "__main__":
    # a live sanity run: the current minute, rebuilt second by second from the tape
    minute = {"key": None, "buys": 0.0, "sells": 0.0, "count": 0}
    last = {"price": 0.0, "qty": 0.0, "side": "-"}

    def on_trade(price, qty, buyer_maker, ms):
        key = ms // 60000
        if key != minute["key"]:
            minute.update(key=key, buys=0.0, sells=0.0, count=0)
        minute["count"] += 1
        if buyer_maker:
            minute["sells"] += qty
            last["side"] = "SELL"
        else:
            minute["buys"] += qty
            last["side"] = "BUY"
        last["price"] = price
        last["qty"] = qty

    async def report():
        while True:
            await asyncio.sleep(1)
            volume = minute["buys"] + minute["sells"]
            delta = minute["buys"] - minute["sells"]
            print(f"  {time.strftime('%H:%M:%S')}  {last['price']:8.2f}  "
                  f"{last['side']:4} {last['qty']:7.2f}  "
                  f"vol {volume:8.2f}  delta {delta:+8.2f}  trades {minute['count']:4}", flush=True)

    async def main():
        await asyncio.gather(stream(on_trade), report())

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\ntape stopped")
