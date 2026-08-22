# 3 — What the operator actually sees

*A walkthrough of the feature as experienced, before any code.*

---

## 3.1 The flow

```
   [ Run live ]  clicked
        |
        v
   PRE-FLIGHT  checking cached inputs, conflicts and quota...      (~0.3s)
        |
        v
   +--------------------------------------------------------------+
   |  PRE-FLIGHT   [1 warn] [3 info]                   est ~70s    |   <- layer 1
   |                                                               |
   |  Results will replay canned data, not this storm's imagery.   |   <- layer 1
   |                                                               |
   |  [ Start run ]  [ Cancel ]                                    |
   |                                                               |
   |  > show all 4 findings                                        |   <- layer 2
   +--------------------------------------------------------------+
```

The gate sits between the click and the run. It is not a modal — it appears in
the page, above the stream, and the Cancel button simply removes it.

## 3.2 The three layers

**Layer 1 — the sentence.** One line of plain English, taken from the most
severe finding, describing the *consequence* rather than the fact.

> Results will replay canned data, not this storm's imagery.

It is coloured by severity (red / amber / green) and set larger than the pills
above it, deliberately: the tally is scannable, but the sentence is what
decides the click.

When there is genuinely nothing to say, the sentence says so rather than
disappearing:

> Cached inputs look consistent - nothing to flag.

**Layer 1b — the pills.** `1 warn`, `3 info`, and `est ~70s`. This is the
scan layer: how much is there, how bad, and how long will this take. Counts
belong *here*, next to the sentence — never instead of it.

**Layer 2 — the evidence.** Behind `> show all 4 findings`, a list where every
entry carries a severity pill, a title, and a full paragraph of reasoning
including the physics and the numbers. Nothing is truncated at this level.
This is the layer that makes the top layer trustworthy: if the sentence
surprises you, the argument is one click away.

## 3.3 Real output, from this repository, right now

Both storms, on a clean checkout with no preprocessed imagery:

**2024-10-G4** — `ready: true`, `est 70s`

| Severity | Finding |
|---|---|
| WARN | Results will replay canned data, not this storm's imagery |
| INFO | GOES XRS flare cache missing |
| INFO | DSCOVR L1 solar wind cache missing |

**2024-05-G5** — `ready: true`, `est 70s`

| Severity | Finding |
|---|---|
| WARN | Results will replay canned data, not this storm's imagery |
| INFO | GOES XRS flare cache missing |
| INFO | DSCOVR L1 solar wind cache missing |
| INFO | **Reference CME speed is 65% off the DONKI record** |

**The two storms differ.** That is the single most important property of the
panel, and it was not true of the first version. A gate that says the same
thing every time is a cookie banner: people learn the shape and click past it
without reading. The G5's extra line is what proves the check is looking at
this storm rather than reciting a template.

The full detail behind that G5 line reads:

> The committed reference for this storm says 2200 km/s; DONKI's CME analysis
> measures 1332 km/s. DONKI's own analyses spread by 10-20%, so a gap this wide
> means the reference severity and the observational record are not describing
> the same event speed. Detection is replaying the stub for this run, so this
> source is never read and the disagreement cannot affect the output.

Note the last sentence. It is appended automatically, and it is the panel
demoting its own finding — see [chapter 5](05-the-conflict-rules.md#56-the-stub-replay-demotion).

## 3.4 One button, and why

The first version had **Run**, **Run anyway**, and **Cancel**. The second has
**Start run** and **Cancel**.

Two labels for one behaviour is not a choice, it is ambiguity. Both buttons ran
the pipeline; the only thing distinguishing them was how bad the findings were,
which the panel had already said in words directly above. Presenting it twice
implied a difference in what would happen, and there was none. One label,
always the same word, and the severity lives entirely in the sentence.

## 3.5 It never blocks

Even a `block` finding — the rate limiter, which means the run *will* be
rejected — leaves **Start run** enabled. The panel explains what will happen
and lets you do it anyway.

And if the pre-flight check itself fails for any reason, the gate silently
disappears and the run starts directly:

```js
.catch(() => {
  setGate(null)
  startRunner(runner)
})
```

The rule: **a diagnostic that can break the thing it diagnoses is worse than no
diagnostic.** In a demo product this is not a nicety — a gate that fails closed
would mean a bug in a safety-advisory feature could cost you the entire
presentation.

## 3.6 What is deliberately *not* here

- **No auto-fix.** The panel never offers to fetch the missing cache or clear
  the rate limit. Every one of those is a write, and the whole value of the
  check is that it is read-only ([chapter 6](06-the-read-only-invariants.md)).
- **No remembering.** No "don't show this again". A finding that was worth
  showing once is worth showing again; suppression is how warnings die.
- **No blocking.** Covered above.
- **No spinner theatre.** The check is sub-second after startup warm-up, so the
  loading state is one line of text and usually invisible.

---

Next: [How it works](04-how-it-works.md).
