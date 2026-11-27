# VWAP

**Where the session sits. The LOCATION half of the checklist.**

---

## What it is

```
VWAP = Σ(typical price × volume) / Σ(volume)

typical price = (high + low + close) / 3, per 1m kline,
accumulated from 00:00 UTC to now.
```

Built from Binance's own klines, so it is the market's average price, not ours.

---

## What it returns

```
vwap             the daily line — the one that matters
weekly_vwap      the larger context, from Monday 00:00 UTC
session_high     highest price since 00:00 UTC
session_low      lowest price since 00:00 UTC
prev_day_high    yesterday's high
prev_day_low     yesterday's low
round            nearest 0.5 to the last close
nearest()        which of those is closest, and by how much
```

---

## Why it exists

```
absorption in the middle of a range   noise
absorption at VWAP                    a decision point
absorption at session high/low        a decision point
absorption at yesterday's extreme     a decision point
```

Without location, the footprint tells you a fight happened but not whether
anyone cared.

---

## The test it powers

```
distance ≤ 0.12% of price   AT the level     (checklist passes)
distance ≤ 0.25%            NEAR it          (watch only)
further                     no-man's land   (skip)
```

---

## Cost

```
two kline calls (daily 1m, weekly 15m), cached 60 s
weight ~10 a minute
```

Refreshing every second would be waste — VWAP barely moves late in a day.

## What it is not

Not an indicator to trade on its own. **Trade at it, not because of it.**
