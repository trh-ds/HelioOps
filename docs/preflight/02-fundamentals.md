# 2 — Fundamentals

*For a reader with no background in space weather or software. Everything
here is needed to understand the rest of the pack. Skip if you already know
what a CME and a cache are.*

---

## 2.1 The physics, in four paragraphs

**The Sun throws things at us.** A *coronal mass ejection* (CME) is a billion
tonnes of magnetised plasma launched off the Sun's surface at anywhere from
300 to 3000 kilometres per second. Most miss. Some arrive.

**Arrival takes one to three days.** That gap is the entire reason forecasting
is possible. We see the launch in a coronagraph — a telescope that blocks out
the Sun's disc so the faint outflow around it is visible — and we have a day or
two to act before it hits.

**What arrives causes specific, known problems.** The plasma carries its own
magnetic field. If that field points *southward* it couples to Earth's field
and dumps energy into the upper atmosphere. That energy: ionises the layer of
atmosphere that GPS signals pass through (so positions drift by metres),
absorbs high-frequency radio (so aircraft over the poles lose their only
long-range voice link), and induces currents in long conductors (so grid
transformers heat up). If the field points northward, comparatively little
happens. **Direction matters more than size.**

**Severity is graded on published scales.** G1–G5 for geomagnetic storms,
S1–S5 for radiation, R1–R5 for radio blackouts. G5 is the top. The two storms
HelioOps replays are the October 2024 G4 and the May 2024 G5 — the largest in
two decades.

## 2.2 What HelioOps does with that

Five stages, one after another:

```
solar imagery + public data feeds
   |
   1. DETECTION      is there a CME, how fast, how severe?     -> a "StormEvent"
   2. IMPACT         how much GPS error, how likely a blackout? -> numbers + ranges
   3. ADVISORY       four industry agents write instructions    -> readable steps
   4. VERIFIER       a rule engine corrects unsafe values       -> checked steps
   5. DELIVERY       stream it to the operator's screen
```

The output is not "G4 watch, Kp 8.3". It is *"move flights AAL100 and AAL142
off the polar routes in the next 6 hours; switch HF to 5 MHz; source: ICAO NAT
Doc 007, page 42."* That last mile is the product.

## 2.3 Six software words you need

**Cache.** A local copy of something fetched from the internet, kept on disk so
you do not fetch it twice. HelioOps keeps caches of solar wind readings, CME
records, X-ray flux and space-weather alerts.

**Fallback.** What a program does when its first choice is unavailable. If the
cache is missing, fetch it. If the fetch fails, use a stale copy. If there is
no stale copy, use a hardcoded default. HelioOps has a fallback at every step,
by design — nothing is allowed to crash the demo.

**Stub.** A stored, known-good answer used when the real computation cannot
run. HelioOps ships a stub for each of its two storms: a complete, hand-checked
description of that event, used when no imagery is available. It makes the demo
deterministic. It also means the demo can look identical whether or not it
actually did any work — which is precisely the problem chapter 1 describes.

**Rate limit.** A rule that says "not more than N times per period". HelioOps
allows one pipeline run per storm per thirty seconds, so a stuck browser tab
cannot drain the token budget.

**Token budget / TPM.** Language models are billed and throttled by *tokens per
minute*. Exceed it and requests do not fail — they queue. A run that would take
70 seconds can take three minutes with no error message anywhere.

**Read-only.** A operation that observes without changing anything. Sounds
trivial. Chapter 6 is entirely about how hard it actually was.

## 2.4 Progressive disclosure, explained properly

Progressive disclosure is an interface principle: **show the smallest thing
that lets someone decide, and put everything else one deliberate action away.**

The everyday example is a flight booking site. The result row says *"£214,
2 stops, 11h 40m"*. It does not say *"operated by IB6250 codeshare BA7123,
Airbus A350-900, terminal 4, 32 minutes minimum connection at MAD."* That is
all true, all relevant to someone, and all behind "Details". The row exists to
let you decide whether to click.

The failure modes are symmetrical and both common:

- **Too little.** *"3 warnings."* A number is a tally, not information. You
  cannot decide from it, so you must expand — which means the top layer bought
  you nothing.
- **Too much.** The full evidence up front. Everything is visible and nothing
  is legible, so people learn to click past it. This is how cookie banners
  became invisible.

The thing that makes it work is that the top layer must be **decision-shaped**:
it answers the question the user is actually holding, in the form they need.
Here that question is *"should I press Run?"*, so the top layer is a sentence
about consequence — see [chapter 3](03-what-the-operator-sees.md).

## 2.5 "Detect conflicts early" — what a conflict is here

Not a merge conflict, and not an error. A **conflict** in this system is *two
independent data sources describing the same event in ways that cannot both be
true.*

An analogy: two witnesses to the same car accident. One says the car was doing
30, the other says 80. Neither statement is malformed. Neither witness is
obviously lying. But you now know something you did not know from either
statement alone — **one of them is wrong, and you should find out which before
you act on either.**

That is exactly the check. It cannot be done by validating one file. It only
appears when you put two next to each other and ask whether physics allows
both.

---

Next: [What the operator sees](03-what-the-operator-sees.md).
