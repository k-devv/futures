# What the docs gave us — checked against the live API

Everything below was called tonight against the demo account and the production market
data host. Nothing here is from memory.

---

## 1. Two hosts, not one

```
demo-fapi.binance.com    account, orders, positions, fills, brackets
fapi.binance.com         klines, aggTrades, depth, open interest, taker ratio, funding
```

The demo host answers market data (`aggTrades`, `depth`) but **does not serve `/futures/data/*`**.
Those five metric endpoints exist only on the production host. `api.py` now routes by name.

---

## 2. The five pieces of data a footprint never had

### a. Taker buy/sell volume — `/futures/data/takerlongshortRatio`

```json
{"buySellRatio": "2.8813", "buyVol": "296.3100", "sellVol": "102.8400", "timestamp": 1795725900000}
```

Binance's own taker buy vs sell volume per 5 minutes. This is **the same delta we compute**, but
from the exchange's books instead of our websocket. Two uses:

```
validate    if our delta and their ratio disagree badly, our tape has a hole
context     a 5m ratio of 2.88 means buyers dominated the whole period, not just our bar
```

### b. Open interest — `/futures/data/openInterestHist`

```json
{"sumOpenInterest": "505406.26", "sumOpenInterestValue": "281226...", "timestamp": ...}
```

**This is the missing half of absorption.** Absorption is effort without result: size traded, price
not moving. Open interest tells us whether that size stayed (new positions) or was just handed over.

```
OI rising + price flat at the level     real absorption, somebody is eating the flow
OI falling + price flat                 position closing, not absorption — skip
OI flat                                 churn, the level is not being defended
```

Periods: 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d. History: 30 days, 500 rows max.

### c. Order book depth — `GET /fapi/v1/depth` and the `@depth20@100ms` stream

Confirmed live: 20 levels, ten times a second, and it never needs a REST snapshot to stay in sync
(partial book depth).

```
bids stacked under the level and not pulled      the level is being defended — with absorption, this is the trade
asks stacked above and eaten                     supply being consumed — the other side of the same fight
one side thinning as price arrives               the level is about to break — do not fade it
```

### d. Liquidations — `!forceOrder@arr`

A liquidation is aggressive flow that is **not** a trader's opinion: it is a position being closed
by the exchange. In a footprint it looks exactly like absorption, and it is the most common false
signal at a level.

```
if a liquidation prints in the same second as an "absorption"    treat it as forced flow, not defence
```

### e. The trade stream that actually works

```
bnbusdt@trade        works, every fill, 15 messages per second on BNB
bnbusdt@aggTrade     connected, then delivered nothing in 8 s on BNB, ETH and BTC
bnbusdt@bookTicker   works, best bid and ask
bnbusdt@depth20@100ms works, 20 levels ten times a second
!forceOrder@arr      connected, delivered nothing in 40 s
bnbusdt@forceOrder   connected, delivered nothing in 30 s
```

`@trade` is what the footprint must read. Its payload:

```json
{"e":"trade","T":1795726073217,"s":"BNBUSDT","t":2338023459,
 "p":"556.460","q":"0.46","X":"MARKET","m":true,"st":1}
```

`st` is not in the documented schema. Do not build on it.

The liquidation streams stayed silent in the window we tested, so liquidation labelling is
**unverified** — useful in principle, not to be wired in until we have seen one payload.

### f. RPI trades — isRPITrade, and nq in aggTrades

```
{"p": "556.71", "q": "683.50", "nq": "683.50", "isBuyerMaker": false, "isRPITrade": false}
```

RPI = retail price improvement: flow routed through a retail programme, filled better than the book.
`q` is the total, `nq` the part that is **not** RPI. For a footprint this matters: RPI prints are
retail flow, and they can fill a level without meaning anything about supply and demand.

```
q - nq   how much of the print was retail
```

`/fapi/v1/trades` returns `isRPITrade` per trade; `aggTrades` returns `nq`; the historical CSV files
do not, so backfills cannot separate them.

---

## 3. Free full history for backtesting

```
https://data.binance.vision/data/futures/um/daily/aggTrades/BNBUSDT/BNBUSDT-aggTrades-2026-11-25.zip
```

Verified: HTTP 200, 5.1 MB for one day of BNBUSDT. That is the entire tape, per day, free, no key.
This is how the absorption rules get tested against months of data instead of one night of hope.

---

## 4. Things that bite, from the changelog and from tonight

```
2025-12-09  STOP_MARKET / TAKE_PROFIT_MARKET moved to /fapi/v1/algoOrder
            old endpoint answers -4120. We hit it, and now bracket through algoOrder.
2026-11-26  v1 endpoints do get decommissioned (portfolio account today)
            so the ENDPOINTS table is the only place a change should land.
tonight     orphan brackets: eight srv-… algo orders left resting with no position.
            cancelled by hand. The engine must cancel its brackets when it flattens.
tonight     two engines on one account produced two entries for one signal.
            one engine, one process, one account.
```

---

## 5. What this changes in our own system

```
add    open interest at the level          the difference between absorption and churn
add    taker ratio as a 5m sanity check    catches a broken websocket immediately
add    depth20@100ms                       defence or thinning, visible live
add    forceOrder                          labels forced flow so it is not read as absorption
add    isRPITrade / nq                     splits retail print out of the tape
keep   algoOrder brackets                  the only supported way to hold a stop
keep   one signed file                     ten endpoints, not one hundred and thirty
```

---

## 5b. Round two: the checks that prove the footprint is honest

### Our delta equals Binance's delta, exactly

Every kline carries `volume` (field 5) and `taker buy volume` (field 9), so:

```
delta = 2 * takerBuy - volume        (the taker sells are the rest of the volume)
```

Measured on five consecutive live minutes, comparing that against the same minute rebuilt from
`aggTrades`:

```
minute   kline volume   derived delta   tape delta   difference
20:52        84.74          -9.100        -9.100      +0.000
20:53        35.72         -12.740       -12.740      +0.000
20:54        65.56         -42.700       -42.700      +0.000
20:55       217.59        +158.590      +158.590      +0.000
20:56        39.23         -14.770       -14.770      +0.000
```

**Zero difference to three decimals.** One kline call now proves whether our websocket dropped
anything, per minute. `footprint.check_against_kline()` does that.

### Open interest can be polled per bar, not only every 5 minutes

```
/fapi/v1/openInterest     weight 1 per call, moves every few seconds
measured: 505,210.68 -> 505,215.35 in 20 s, then flat
```

`/futures/data/openInterestHist` only gives 5m buckets. Polling the plain endpoint gives the OI
change **inside a single 1m bar** — far more useful for judging absorption.

### Depth: how far 20/100/500 levels actually reach

```
limit  20   0.39 USD around price   weight 2
limit 100   1.99 USD               weight 5
limit 500  10.68 USD               weight 10
```

20 levels is too thin to judge a level 0.5 away. `limit=100` covers ±1 USD and costs weight 5,
so a snapshot every 5 seconds is 60 weight a minute — safe inside 2400.

### The absorption score, from the bar alone

```
1  the row is 3x the bar's median row
2  it is the POC of the bar
3  the close rejected it by more than the bucket
4  the POC sits in the wick (price fought there and lost)
5  the next bar did not accept through the absorbed bar
```

### RPI is empty on BNB

`aggTrades` has `q` and `nq` (not-RPI), `/fapi/v1/trades` has `isRPITrade`. Measured across
several minutes of BNB: **0.0% RPI**. The field exists; the flow does not, for this symbol.
`footprint.rpi_share()` reports it so we notice if that ever changes.

## 6. One command to see it all

```npython binance/endpoint/api.py snapshot
```n
 prints price, funding, open interest and its 5-minute change, the taker ratio, book imbalance,
 and the retail share of the last 200 trades - in one call, from the two hosts.

## 7. What the docs did not give

```
absorption         no endpoint, no derived metric. It stays our own read of the tape.
POC / value area   no endpoint. Ours.
HELD / EATEN       no endpoint. Ours.
```

So the edge is still ours to build. What Binance adds is **the other half of the evidence**:
open interest, the book, liquidations, and retail-vs-real flow.
