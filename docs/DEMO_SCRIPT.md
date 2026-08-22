# HelioOps — Demo Video Script

**Target: 5:00.** Read-aloud copy in the right column, what to have on screen in
the left. Every beat pairs a thing the product *does* with the engineering
decision that made it possible — so the video works for a product judge and a
technical judge without switching modes.

**Before you hit record**

- Backend warm (`uvicorn`), frontend on `localhost:3000`, **one run already
  completed** in a second tab so you can cut to finished advisories instead of
  waiting 80 seconds on camera.
- Groq key pool loaded — four keys, four TPM budgets.
- Browser zoom 110 %, console at 1920×1080, notifications off.
- Have `nat_doc_007_2025.pdf` closed. You will open it *from the product*.

**Timing marks are cumulative.** If you overrun, cut §6 (the chatbot) — it is
the only section that is not load-bearing for the core claim.

---

## §1 — The problem (0:00 → 0:40)

**Screen:** landing page, slow scroll. Then the PROBLEM page, the four-industry
table.

> When the Sun throws a coronal mass ejection at Earth, four industries lose
> capability within hours. Polar flights lose HF radio. Grid operators get
> induced currents cooking transformers. Ships lose GMDSS distress comms.
>
> And here's the thing — the data is already free. NOAA publishes the alerts.
> NASA publishes the CME kinematics. GOES publishes the flare class. All public,
> all real time.
>
> What does not exist is the last mile. "G4 watch, Kp 8.3" tells a dispatcher
> nothing about *which of their forty polar flights to move*. The actual
> procedures live in ICAO NAT Doc 007, NERC TPL-007-4, IMO GMDSS — hundreds of
> pages nobody reads at 3am during an event.

**Architectural note to land:** *none*. This section is pure problem. Resist
the urge to mention the stack.

---

## §2 — What it does, in one run (0:40 → 1:30)

**Screen:** dashboard, storm `2024-10-G4` selected. Click **Run**.

> So we built the last mile. One click, one storm.

**Screen:** the pre-flight panel appears. **Pause here — do not click through.**

> And the first thing that happens is *not* the run.
>
> This is pre-flight. Before it spends eighty seconds, the system tells you what
> it's about to do: which data sources are cached and which will fall back to a
> stub, whether the cached sources physically contradict each other, and whether
> the token budget will stall halfway.

**Screen:** expand the findings.

> On this storm it's clean. On the G5 it isn't — it flags that our reference
> speed is sixty-five percent off what DONKI actually measured.

> **[ARCHITECTURE]** Two decisions in that panel. It is strictly read-only — it
> `stat`s every cache file before any parser touches it, because our ingestion
> clients are cache-first-then-*network* and would silently fetch. And it uses a
> non-mutating `peek` on the rate limiter, because the normal check *records*
> the call — so merely asking "can I run?" would have consumed the run slot.
>
> It also never hard-blocks. It warns, and there's always a "start run".
> A diagnostic that can break the thing it diagnoses is worse than no diagnostic.

**Screen:** click **Start run**. Let the stream begin, then cut.

---

## §3 — The pipeline, live (1:30 → 2:20)

**Screen:** the WebSocket stream — stage events, agents thinking in parallel.

> Five stages, streaming over a WebSocket as they happen.
>
> Detection first. That's a threshold algorithm on running-difference
> coronagraph frames — **no neural network, no random seed.** Same frames in,
> byte-identical output every single time.

> **[ARCHITECTURE]** That's deliberate. We had a CNN. We deleted it — because no
> labelled CME dataset exists at the size that would justify one, and NASA's
> DONKI already publishes human-reviewed kinematics. We are not going to train a
> regressor to guess a number a NASA API already publishes and a regulator would
> accept.

**Screen:** impact numbers appear with intervals.

> Then impact. Six LightGBM models — three quantiles, two targets. Which means
> the operator is told "GPS error 11.2 metres, 95 % confidence interval 6.8 to
> 13.7", not a bare number with invisible error bars. A dispatcher plans against
> the worst case, not the average.

> **[ARCHITECTURE]** And we measured whether that interval means what it claims.
> Coverage is 95.9 % and 94.2 % against a nominal 95 %, at a narrow width. We
> report that pair together on purpose — coverage alone is trivially gamed by
> predicting minus-infinity to infinity.

**Screen:** four agents streaming at once.

> Then four industry agents in parallel, each grounded by retrieval over the
> real rulebooks.

---

## §4 — The verifier (2:20 → 3:10) — **the centrepiece**

**Screen:** an advisory card with a verifier correction visible.

> This is the part I most want you to see.
>
> The agent wrote "switch HF to 21 megahertz". That is a plausible-sounding,
> completely wrong answer — 21 is not in the ICAO North Atlantic set.
>
> A rule engine downstream of the model caught the number, tested it against
> `{3, 5, 8, 11, 17}`, rejected it, **rewrote the action to 5 megahertz**, and
> recorded the correction. The operator sees both — what the model proposed, and
> what the rules enforced.

> **[ARCHITECTURE]** There is no LLM anywhere in that step. It's a regex and a
> constant set. Anyone can wire a language model to a vector store — almost
> nobody puts a deterministic engine behind it that *rewrites* the unsafe value
> instead of flagging it and hoping someone reads the flag.
>
> A wrong HF frequency in an aviation advisory isn't an embarrassing
> hallucination. It's a safety incident.

---

## §5 — Provenance you can click (3:10 → 3:50)

**Screen:** hover a citation in an action item, then click it. The PDF opens **at
the cited page**.

> Every action cites a source. And the citation is a link.

**Screen:** the PDF, open at page 42. Let it sit for two seconds.

> That's the actual ICAO document, open at the actual page the model read.
> Not the filename — the page.

> **[ARCHITECTURE]** That was not a frontend job. The page number was being
> destroyed at *ingest* time: we joined every page of the PDF into one string
> before chunking, so by the time anything reached the database the location was
> gone. We re-chunked page by page and carried the number through — which meant
> also fixing two silent bugs it exposed: every ingest script was overwriting the
> metadata dictionary the page lived in, and a rebuild was *accumulating*
> instead of replacing, so the corpus had silently gone from 918 chunks to 1641
> with stale duplicates mixed in.
>
> We measured retrieval quality before and after. Worst case moved by two
> hundredths. That's the cost of chunks no longer spanning page boundaries, and
> it's a fair trade — a citation that straddles two pages can't point at either.

**Screen:** the six-step provenance trace.

> Underneath, every advisory carries the full chain: raw data, detection,
> impact, retrieval, verifier, output. A regulated operator can't act on
> something they can't trace.

---

## §6 — Ask the agent (3:50 → 4:20) — *cut this first if long*

**Screen:** expand "Ask the aviation agent about this advisory". Type: *"What
causes HF disturbances on North Atlantic routes?"*

> Each agent will answer questions about its own advisory.

**Screen:** answer arrives with citations.

> Grounded, cited, and those citations are the same clickable links.

**Screen:** now ask something out of scope — *"Which HF frequency for polar
flights at G4?"* — and let it refuse.

> And when the knowledge base doesn't cover it, it says so, instead of inventing
> a frequency. Which is the entire posture of the system in one answer.

> **[ARCHITECTURE]** It runs on a *different model* from the advisory pipeline —
> a 20B rather than the 120B. Groq meters throughput per key *and* per model, so
> chat draws from a separate budget and can never starve a live run. And any
> citation the retrieval didn't actually return gets filtered out before it
> reaches you — otherwise you'd click it and get a 404.

---

## §7 — What we'd tell you before you deployed it (4:20 → 4:45)

**Screen:** the ABOUT page, "Current maturity, stated plainly".

> One thing we won't do is oversell it.
>
> The impact models are trained on synthetic storms — physics-shaped rules we
> wrote. So the R² measures how well the model recovered *our rules*, not
> forecast skill, and we don't quote it as a headline. We built the real-data
> track against NASA OMNI two, and then deleted it: OMNI publishes every driver
> and no label, and the labels we'd need aren't published in the form we'd need.
> It was blocked, not unfinished. Fifteen hundred lines gone.
>
> The interval calibration and the physics ordering gate — those are real, and
> those we do quote.

> **[ARCHITECTURE]** We deleted a lot. A Kubernetes and Terraform stack, because
> an EKS cluster for two containers was the single biggest cost in the project
> and it contradicts scale-to-zero. Two agent frameworks, for a forty-five line
> wrapper. A Redis cache for a command nobody runs twice.
>
> A repo that only ever grows is a repo where nothing was ever evaluated.

---

## §8 — Close (4:45 → 5:00)

**Screen:** the hero pipeline diagram, or the dashboard with four advisories.

> Free public data in. A deterministic detector. Calibrated uncertainty. Four
> grounded agents. A rule engine that has the last word. And an operator who can
> click any instruction and read the page it came from.
>
> Runs on a CPU. Zero GPU hours.
>
> HelioOps — because "G4 watch, Kp 8.3" is not a decision.

---

## Appendix A — Architectural decisions, ranked by how much they land

Use these to answer questions after the video. Ordered by impact on a technical
judge, not by how hard they were.

| # | Decision | The line that sells it |
|---|---|---|
| 1 | **Deterministic verifier downstream of the LLM** | "It rewrites the value. It doesn't flag it and hope." |
| 2 | **Deleted our own CNN** | "No labelled data exists at that size, and DONKI already publishes reviewed kinematics." |
| 3 | **Quantile regression, coverage measured** | "95.9 % against a nominal 95 %, and we report the width alongside it because coverage alone is gameable." |
| 4 | **Page-accurate citations** | "The blocker was at ingest, not in the UI — we were destroying the page number before it ever reached the database." |
| 5 | **Chat on a separate model** | "Different TPM bucket. Chatting can't starve a run." |
| 6 | **Pre-flight is read-only and never blocks** | "Checking whether you may run used to consume the run slot." |
| 7 | **Adapters, and we deleted the ports layer** | "One interface per implementation is ceremony. A test enforces the boundary." |
| 8 | **Every layer degrades, none raise** | "No frames → stub. No Groq → escalate to specialist. Never a guess." |
| 9 | **Deleted the k8s/Terraform stack** | "Biggest line item in the project, for two containers, against a scale-to-zero target." |
| 10 | **Hard-coded severity matrix** | "G4 always means CRITICAL for aviation. Never HIGH because a sampler rolled differently." |

## Appendix B — Hostile questions, and the honest answer

**"Your R² is 0.98 — isn't that suspiciously high?"**
Yes, and it's circular. The models are fit to synthetic rows generated from
rules we wrote, so R² measures rule-recovery. That's why we lead with interval
calibration instead, which isn't circular.

**"Isn't the verifier just a regex? That's not impressive."**
It's a regex against a regulatory constant set, and that's the point. The
impressive part isn't the implementation, it's that it sits *downstream of the
model* and has authority to overwrite it.

**"What if the LLM cites a document that doesn't exist?"**
Citation resolution runs against the chunks retrieval actually returned. An
unresolvable citation raises `CITATION_GAP` and costs the advisory confidence.
In chat, it's dropped before it reaches the operator.

**"Two demo storms isn't a product."**
Correct. Live mode exists; the cached path is what the demo runs. We'd rather
show you two storms that replay deterministically than one that might not.

**"Why not stream the chatbot response?"**
The 20B answers in a couple of seconds and a spinner covers it. It's on the
deferred list, not the done list.
