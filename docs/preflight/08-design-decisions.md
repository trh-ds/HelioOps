# 8 — Design decisions, and the roads not taken

*Every decision here had at least one defensible alternative. This chapter names
the alternative before defending the choice.*

---

## 8.1 Why a gate at all, rather than reporting after the run

**The alternative.** Run immediately, and show which fallbacks fired in the
result. Cheaper, no new endpoint, no new interaction.

**Why the gate wins: cost asymmetry.**

| | Cost |
|---|---|
| Pre-flight check | ~0.3s, no quota, no side effects |
| The commitment it guards | 65–80s, metered tokens, 30s lockout, uncancellable |

A confirmation step in front of a cheap, reversible action is friction — it is
why "are you sure?" on a delete-one-email is universally hated. In front of an
expensive, effectively irreversible one it is the difference between finding out
before and finding out after.

The post-hoc alternative also has a subtler failure: by the time the result is
on screen, the operator is reading advisories. A note saying "detection replayed
canned data" competes for attention with the thing they came for, and loses.

**Where the alternative is genuinely better:** if the run were 3 seconds and
free, the gate would be pure friction and should be deleted.

## 8.2 Why it never hard-blocks

**The alternative.** Refuse to run when there is a `block` finding. It is the
safer-sounding choice, and in a regulated production system it might be right.

**Why it is wrong here, twice over.**

*Product:* this is a demo tool built for a live presentation. A gate that fails
closed means a bug in a diagnostic can cost the entire demo. The failure mode of
blocking is strictly worse than the failure mode of warning.

*Principle:* the operator has context the check does not. "Rate limited, wait
22s" is information; deciding on their behalf that they may not proceed is not
safety, it is presumption. The check's job is to inform the commitment, not to
own it.

This extends to the check failing entirely:

```js
.catch(() => { setGate(null); startRunner(runner) })
```

**A diagnostic that can break the thing it diagnoses is worse than no
diagnostic.** If pre-flight throws, the run starts as if the feature did not
exist.

## 8.3 Why the headline is a sentence, not a count

**The alternative — and the first version's actual behaviour.** Layer one was
`3 warnings, 1 info`.

**Why it was replaced.** A count is a tally, not information. It tells you how
much there is to read, not what any of it means, so it cannot decide the click —
which means you must expand, which means the top layer bought you nothing. It
also treats all warnings as fungible when they are not: one "detection will
replay canned data" matters more than three missing optional caches.

The sentence answers the question the operator is actually holding:

> Results will replay canned data, not this storm's imagery.

The counts did not disappear — they moved next to the sentence as pills, where a
tally is exactly the right shape. **Scan layer and decide layer, in that order,
both visible.**

## 8.4 Why one button label

**The alternative — and, again, the first version.** `Run` when clean,
`Run anyway` when there were findings, plus `Cancel`.

**Why it was replaced.** Both labels ran the pipeline. The only thing that
differed was the severity of the findings, which the panel had already stated in
words directly above the button. Two labels for one behaviour reads as a
difference in outcome, and there was none — it was ambiguity dressed as
nuance.

One label, always the same word. Severity lives entirely in the sentence and the
pills, where it can be stated precisely.

## 8.5 Why reuse the ingestion parsers

**The alternative.** Write light-weight readers inside `preflight.py` — faster,
no import of the CV layer, no risk of a parser side effect.

**Why reuse wins.** A prediction that uses different code than the thing it
predicts can disagree with it, and every such disagreement is a bug that only
appears in production. Reusing `select_best_cme`, `cme_to_fields`,
`fetch_and_classify_flare` and `fetch_l1_wind` makes an entire class of "the
check said fine but it wasn't" structurally impossible.

The cost is precisely the trap in [chapter 6](06-the-read-only-invariants.md):
those parsers fetch and write when the file is absent. That cost is paid once,
by the stat-before-parse invariant, and pinned by a test. Paying a known cost
once beats accepting an unbounded class of divergence bugs forever.

## 8.6 Why `gateDecision()` is a separate pure module

**The alternative.** Keep it inside `Dashboard.jsx` where it is used.

**Why it moved out.** It is the only branching logic in the gate — severity
sort, headline selection, counts, the fall-through to `{action:'run'}`. In its
own module with no React and no DOM, it is assertable from `data.test.mjs` with
plain node asserts, in a frontend that has three runtime dependencies and no
test framework. Adding vitest and jsdom to test twenty lines of sorting would
have cost more than the feature.

The general principle: **push the decisions out of the component and into a
function, then test the function.** The component that remains is rendering,
which is the part least worth unit-testing anyway.

## 8.7 Why severities are demoted rather than hidden

Covered mechanically in [5.6](05-the-conflict-rules.md#56-the-stub-replay-demotion);
the decision is worth stating on its own.

Under stub replay, a real conflict cannot reach the output. Three options:

| Option | Problem |
|---|---|
| Leave it `warn` | An amber pill for something with no path to the result. Erodes what `warn` means. |
| Drop the finding | Suppressing true information because it is currently inert. It never comes back. |
| **Demote and explain** | Chosen. |

The third keeps two properties simultaneously: the severity scale continues to
mean *"this can change what you get"*, and nothing true is thrown away. The
appended sentence makes the demotion self-explaining rather than looking like an
inconsistency between the pill and the prose.

## 8.8 The alternatives to the whole design

Honest comparison. The gate is defensible, not uniquely correct.

| Approach | Argument for | Why not chosen |
|---|---|---|
| **Confirmation gate** (chosen) | Ties findings to the specific action, at the moment of commitment | Interstitial; one extra click every run |
| Post-run reporting | No new interaction at all | Operator already spent the 80s; competes with the result for attention |
| Hard block on conflicts | Sounds safest | Wrong for a demo, and presumptuous in general — the operator has context the check does not |
| Always-on health panel | No click needed; better for a 24/7 console | Ambient state does not tie a finding to *this* run of *this* storm |
| Tooltip on the Run button | Lightest possible | Cannot carry evidence; nowhere to put the paragraph of physics |

The one worth arguing about is the **always-on panel**. For a real operations
console staffed continuously, ambient state genuinely might beat an
interstitial — the operator would rather see degradation the moment it appears
than at the moment they happen to click. The gate wins here because HelioOps is
demo-and-replay oriented: sessions are short, the click is the whole
interaction, and the findings are specific to the storm just selected.

If HelioOps became a real 24/7 console, revisiting this is the first thing to
do.

## 8.9 What "substantial without a rebuild" bought

The brief asked for scope that fits 24 hours and does not require a rebuild.
The final shape:

- **Nothing in the pipeline changed.** No new stage, no schema change, no new
  WebSocket event — which mattered, because `TestStreamEventContract` pins
  `pipeline.complete` as the last event of a run.
- **No new dependency**, backend or frontend.
- **One new module, one new route, one new component, one new pure helper.**
- **Two data files committed** (44 KB) and two directories gitignored.

The check is entirely additive: delete `preflight.py`, the route, and the gate,
and the product returns exactly to its prior behaviour. That is the property
"without a full rebuild" is really asking for — not a line count, but a clean
seam.

---

Next: [Testing](09-testing.md).
