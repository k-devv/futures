# IMBALANCE

**Resting money around the price. The present tense of absorption.**

---

## What it is

```
IMBALANCE = (bids − asks) / (bids + asks)
            over every level within ±0.30 USD of the mid price
```

```
+0.12   twelve percent more money resting on the bid side
-0.18   eighteen percent more on the ask side
 0.00   balanced
```

---

## Why it exists

```
BALLAST     positions that stayed during the bar      history
IMBALANCE   money still resting there right now       present
```

A footprint can show a fight, and BALLAST can show that positions stayed — while
the book has already been pulled. IMBALANCE catches that:

```
absorption + BALLAST up + imbalance positive   the defender is there
absorption + BALLAST up + imbalance negative   the defender left
```

It updates every 10 s, so it warns while the bar is still forming.

---

## How it is measured

```
GET /fapi/v1/depth?limit=100    weight 5, polled every 10 s
```

100 levels reaches roughly 1 USD each side at BNB prices — the smallest depth
that still covers a level 0.30 USD away without paying for 500 rows.

**Cost:** weight 5 every 10 s = 30 a minute, 1.25% of the 2400 budget.

---

## Where it sits in the read

```
POC         where the fight was
BALLAST     who stayed
IMBALANCE   who is still standing there
```

---

## What it cannot do

```
no history      Binance does not archive the book at a price level.
                bookDepth archives depth by % from mid, not around a level.
                bars older than this process carry imbalance: null.
one sample      change is 0 and samples: 1 - visible, not hidden.
no data         the page draws nothing. never a zero.
```
