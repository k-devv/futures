# BALLAST

**Open interest, read per 5m bar. The question the footprint cannot answer.**

---

## What it is

```
BALLAST = open interest at the end of the bar  −  open interest at its start
```

Two numbers from Binance, one subtraction. Nothing derived, nothing modelled.

---

## Why it exists

The footprint shows that size traded at a price. It cannot show whether that size
**stayed**. Open interest can.

```
price flat  +  BALLAST up      positions opened and held    → somebody is absorbing
price flat  +  BALLAST down    positions closed             → churn, the level is hollow
price moves +  BALLAST up      new money pushing            → the move has weight behind it
price moves +  BALLAST down    old money leaving            → the move is a squeeze
```

Absorption without BALLAST is a guess. With it, "heavy row" becomes "heavy row and
the size is still standing there".

---

## Where the numbers come from

Binance has **no open-interest websocket**. There are two honest sources, and this
module uses both:

| source | endpoint | used for | cost |
|---|---|---|---|
| live snapshot | `GET /fapi/v1/openInterest` | the bar being formed, polled every 10 s | weight 1 |
| official series | `GET /futures/data/openInterestHist` | bars that closed before we started, and backfills | weight 1 |

**Preference order per bar:**

```
1  polled samples   taken while the bar was forming - closest view
2  official series  the same window, sampled by Binance
3  None             no data. the page draws nothing, never a zero
```

---

## Files

```
BALLAST/
└── ballast.py     every function documented: input, output, cost, failure mode
```

**Functions**

```
open_interest_now(symbol)      one live snapshot
history(symbol, period, limit) the official series
start(symbol)                  begins the 10 s poll, once per process
from_samples(window)           BALLAST from what we polled
from_history(window, rows)     BALLAST from Binance's series
attach(bars, symbol)           puts BALLAST on bars, poll first, history second
summary()                      health line: windows held, poller alive
```

---

## How it reads on the chart

```
POC        where the fight was
HELD/EATEN  who won
BALLAST     whether they are still standing there
```

---

## What it will never claim

```
a bar with one sample    change is 0 and samples: 1 - visible, not hidden
a bar with no data       ballast: null - the page shows nothing
a silent poller          summary().polling says so
```

The rule of the whole system applies here too: **if Binance did not say it, we do
not draw it.**
