# 1 — The problem we found

*Written for anyone. No code in this file.*

---

## 1.1 What the Run button used to be

HelioOps has one button that matters. You pick a storm, you press **Run**, and
the system does five things in sequence: looks at solar imagery and works out
what the Sun threw at us, predicts what that does to GPS and radio, asks four
industry agents to write advisories grounded in the real regulatory rulebooks,
runs a rule engine over what they wrote to correct anything unsafe, and streams
the result to your screen.

That takes **65 to 80 seconds**. Almost all of it is the language model
thinking. While it runs:

- **Money is spent.** The advisory pass burns metered tokens against a fixed
  per-minute budget. Spend it and you wait for the window to roll over.
- **You are locked out.** One run per storm per thirty seconds. Press Run
  twice and the second press is refused.
- **You cannot cancel it.** There is no stop button. Once it starts, it runs.

So the click is a commitment. Not a catastrophic one — nothing explodes — but
an expensive one, and an irreversible one for at least the next half-minute.

## 1.2 The design choice that created the problem

HelioOps is built on a rule its own project memory states out loud:

> Every external client is cache-first: cache hit → disk, miss → fetch + write,
> network failure → stale cache → hardcoded fallback dict. **Never raise to the
> caller.**

This is a good rule. It is why a judge can clone the repo on conference wifi
and get a working demo. Nothing in the pipeline hard-fails: no imagery falls
back to a stored copy of the storm, no CME record falls back to a reference
speed, no solar wind data falls back to 400 km/s and a neutral magnetic field,
no language model falls back to a template advisory.

But a system that never fails is a system that never *tells you* it failed.
Every one of those fallbacks was a single line in a log file:

```
WARNING  no preprocessed frames - returning stub StormEvent
WARNING  L1 fetch produced no usable reading - using fallback defaults
WARNING  DONKI returned no CME in window - using stub speed
```

Nobody reads a log file during a demo. The operator sees a confident advisory
either way. **The failure mode was not "it breaks" — it was "it lies by
omission."**

## 1.3 The specific ways it could quietly be wrong

Every one of these produced a complete, confident-looking result:

| What silently happened | What you saw | Why it matters |
|---|---|---|
| No preprocessed imagery on disk | A normal advisory | The detector never looked at this storm. It replayed a stored answer. |
| Solar wind cache unreadable | A normal advisory | The severity calculation used placeholder numbers, not measurements. |
| Knowledge base empty | An advisory with no citations | The agents were writing ungrounded prose. |
| Token budget exhausted | A very slow run | It does not fail. It *stalls*, silently, for up to a minute. |
| Rate limiter still cooling down | An error, after the click | You spent the click to learn you could not spend the click. |
| ML checkpoints missing | Impact numbers | Conservative defaults, presented identically to real predictions. |

## 1.4 The second problem: nobody was comparing the sources

HelioOps reads from four independent places — a coronagraph reference record,
NASA's CME catalogue, GOES X-ray flux, and DSCOVR's solar wind monitor at the
L1 point. Each one was validated *on its own*: is the file there, does it
parse, does it contain a number.

Nothing checked whether they **agreed with each other**.

That is where the interesting failures live. A file can be present, parse
cleanly, contain a perfectly reasonable number, and still be describing a
different event than the file next to it. Two examples that are real, not
hypothetical:

- The reference record for the May 2024 storm says the CME left the Sun at
  **2200 km/s**. NASA's own analysis of the same event measures **1332 km/s**.
  Both files are valid. They disagree by 65%.
- The solar wind files named for 2024 storms actually contain data from
  whatever day they were downloaded, because the endpoint they came from only
  serves the last few days and ignores the date you ask for. Every field
  parses. Every number is real. None of it is about the storm.

Neither of those is detectable by looking at one file. Both are obvious the
moment you hold two files side by side.

## 1.5 What the brief asked for, and why it fit

> Extend the MVP with a capability related to showing detail gradually rather
> than all at once. Specifically, detect conflicts early and present them
> before the user commits to an action.

The two halves of that brief map exactly onto the two problems above:

- *"detect conflicts early"* → compare the sources against each other, and do
  it **before** the eighty seconds, not after.
- *"showing detail gradually"* → the answer to "what is wrong" is a paragraph
  of physics; the answer to "should I press Run" is one sentence. Show the
  sentence. Keep the paragraph one click away.

The scope constraint — *substantial but not a rebuild* — was satisfiable
because everything needed already existed. The pipeline already knew where
every cache file lived. The ingestion layer already had parsers for all of
them. The health system already knew what was degraded. Nothing had to be
rebuilt; something had to be **read without running it**.

That is the whole idea: **a dry run.**

---

Next: [Fundamentals](02-fundamentals.md) if you want the background, or
[What the operator sees](03-what-the-operator-sees.md) if you want the result.
