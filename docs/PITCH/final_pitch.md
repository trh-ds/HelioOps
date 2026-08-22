# HelioOps — Round 2 Pitch Script

**Challenge #1001 · Progressive Disclosure: Conflict Check**
**Runtime: 8:45–8:55** · **Presenters: Parshva (open, features, technical depth, close) · Tirth (product walkthrough, live console)**

---

## How to use this document

Three columns of information, in this order for every beat:

- **`SCREEN`** — what is on the recording at that moment. Cuts are marked `[CUT]`, holds `[HOLD]`.
- **`SAY`** — read-aloud copy. Written for the mouth, not the eye. Em-dashes are breath marks.
- **`ANCHOR`** — the one plain sentence a non-technical viewer must leave that beat with. Not read aloud; it is the test of whether the beat worked.

**Graphics.** Eight required + one optional. Each has a complete, self-contained generation prompt in [§ Graphic prompts](#graphic-prompts). Generate all of them before recording — three of the beats do not work without their card on screen.

**Pace.** All copy is timed at **148 words per minute**, which is deliberate-but-not-slow. Do not rush the two `[HOLD]` marks; they are the only places the audience gets to read the screen instead of listening.

**Never named.** No organisation is named as the audience anywhere in this script. Keep it that way if the deck is reused.

---

## Running order

| # | Beat | Speaker | In | Out | Len | Graphic |
|---|---|---|---|---|---|---|
| 0 | Cold open — the storm that cost half a billion | Parshva | 0:00 | 0:25 | 0:25 | — |
| 1 | The vocabulary card | Parshva | 0:25 | 0:57 | 0:32 | **G1** |
| 2 | Why this domain, why unexplored, what it costs | Parshva | 0:57 | 1:57 | 1:00 | **G2** |
| 3 | What we already had — sixty seconds flat | Tirth | 1:57 | 2:57 | 1:00 | **G3** |
| 4 | The brief, and the two failures it names in us | Parshva | 2:57 | 3:47 | 0:50 | **G4** |
| 5 | **Live demo — the gate** | Tirth | 3:47 | 5:17 | 1:30 | live console |
| 6 | Deep dive I — the conflict engine and its tolerances | Parshva | 5:17 | 6:17 | 1:00 | **G5** |
| 7 | Deep dive II — the observer effect | Parshva | 6:17 | 7:07 | 0:50 | **G6** |
| 8 | Deep dive III — relevance as a first-class output | Parshva | 7:07 | 7:42 | 0:35 | **G7** |
| 9 | The same principle, across the whole console | Tirth | 7:42 | 8:12 | 0:30 | live console |
| 10 | The honest note | Parshva | 8:12 | 8:37 | 0:25 | **G9** (optional) |
| 11 | Close — the pattern travels | Parshva | 8:37 | 9:00 | 0:23 | **G8** |

**Speaking split:** Parshva 5:55 · Tirth 3:00.

---

# THE SCRIPT

---

## §0 · Cold open — 0:00 → 0:25 — **PARSHVA**

**`SCREEN`** Black for one beat. `[CUT]` to the HelioOps landing page, globe rising, no UI chrome. No title card yet — the first words land on black.

**`SAY`**

> On the tenth of May, 2024, the largest geomagnetic storm in twenty years hit Earth.
>
> Across twelve American states, GPS-guided tractors stopped mid-field — in the middle of the planting window. One storm. One crop. Five hundred million dollars.
>
> No satellite failed. No grid went down. The systems all worked.
>
> The decisions didn't.

**`ANCHOR`** The damage came from *acting on bad information*, not from anything breaking.

> **`[DIRECTION]`** The last two lines are the hook of the entire pitch. Full stop after "worked." One second of silence. Then "The decisions didn't." — quieter, not louder.

---

## §1 · The vocabulary card — 0:25 → 0:57 — **PARSHVA**

**`SCREEN`** `[CUT]` to **G1 — the vocabulary card**, full frame. Hold it for the whole beat and four seconds past the last word.

**`SAY`**

> Thirty seconds of vocabulary, so nothing after this is a black box.
>
> A CME is a billion tonnes of plasma leaving the Sun. G, S and R are the one-to-five severity scales. Bz is the direction of the arriving magnetic field — southward drives storms, northward doesn't. DONKI, GOES and DSCOVR are public data feeds.
>
> And a stub is a stored answer a system replays when it cannot compute a real one.
>
> Hold on to that last one.

**`ANCHOR`** Nothing that follows depends on prior domain knowledge — and "stub" is going to matter.

> **`[DIRECTION]`** Do not read the card. Read *six of sixteen* terms. The card exists so a non-technical viewer can pause and read the other ten. "Hold on to that last one" is a plant — it pays off in §5.

---

## §2 · Why this domain, why unexplored, what it costs — 0:57 → 1:57 — **PARSHVA**

**`SCREEN`** `[CUT]` to **G2 — the cost card**. Reveal it in three stages if your editor allows: left panel on "single unplanned reroute", right panel on "Lloyd's", bottom strip on "here is the gap".

**`SAY`**

> Space weather is one of the few hazards where the warning is free and the response is not.
>
> Aviation loses HF radio over the poles, and a single unplanned reroute runs into six figures. Grid operators get induced current heating transformers. During that May storm, roughly half of everything in low Earth orbit manoeuvred at once, and collision screening was effectively impossible for days.
>
> The tail is not small either. Lloyd's models an extreme space weather scenario at 2.4 trillion dollars globally. Cambridge researchers put a severe US blackout at 41.5 billion dollars a day.
>
> Now — here is the gap. Almost all of the investment in this field goes upstream: better physics, better models, better forecasts. Almost none goes to the last thirty seconds, where a human being has to commit to an action using four data sources that quietly disagree with each other.
>
> That is the space we work in.

**`ANCHOR`** The science is funded. The moment of decision is not. That is where we are.

> **`[DIRECTION]`** This beat answers four judge questions at once — *what domain, why does it matter, how big is the money, why has nobody done it.* Do not add a fifth idea. The "last thirty seconds" phrase should be delivered slowly; it is the thesis of the submission.

**Source notes for Q&A** (do not read aloud, know them cold):

| Figure | Source |
|---|---|
| ~$500 M US Midwest corn losses, May 2024 | Griffin et al., Kansas State University — GNSS outage across the planting window in the twelve states producing ~one-third of the world's corn |
| ~half of active LEO satellites manoeuvring at once; conjunction screening degraded for days | *Satellite Drag Analysis During the May 2024 Gannon Geomagnetic Storm* (AIAA / arXiv 2406.08617). Same paper: Kp magnitude and duration were poorly predicted **even one day out** |
| €0.21 M – €2.20 M per day, aviation HF blackout reroutes | Xue et al., *Space Weather* (2023) — 2003 Halloween storm effects rerun against 2019 flight data |
| $2.4 trillion global, extreme space weather scenario | Lloyd's systemic risk scenario, 2025 |
| $0.6 – $2.6 trillion, North American grid | Lloyd's, *Solar Storm Risk to the North American Electric Grid* |
| $41.5 bn/day domestic + $7 bn/day international supply chain | Oughton et al., Cambridge Centre for Risk Studies (2017), extreme blackout scenario affecting 66 % of the US population |

---

## §3 · What we already had — sixty seconds flat — 1:57 → 2:57 — **TIRTH**

**`SCREEN`** **G3 — the architecture hero**, then fast cuts into the live product: landing → PROBLEM page (four-industry table) → console with a **pre-completed run** already on screen → the verifier correction row. Roughly one cut every eight seconds. End on the six-step provenance chain.

**`SAY`**

> That's what we built in round one, and I'll do it in sixty seconds.
>
> HelioOps takes free public data — coronagraph imagery, NASA's CME records, GOES flare class, DSCOVR solar wind — and runs five stages.
>
> One: a deterministic detector. No neural network, no random seed. The same frames give byte-identical output every run.
>
> Two: six quantile models, so every impact number ships with a ninety-five percent confidence interval, not a bare guess.
>
> Three: four industry agents write advisories grounded in the real rulebooks — ICAO, NERC, IMO — about a thousand page-numbered chunks.
>
> Four is the one people remember. A rule engine with no model in it. The agent proposes twenty-one megahertz. That is not in the ICAO polar band set. The engine rewrites it to five, and shows the operator both numbers.
>
> Five streams it live, with a six-step audit trail from raw pixel to final instruction.
>
> That's the MVP. Now — the part this round is about.

**`ANCHOR`** They already had a working, auditable pipeline. Round 2 is not a rebuild.

> **`[DIRECTION]`** This is the only beat where speed is a feature. Tirth should be visibly moving faster than Parshva. The 21 MHz → 5 MHz correction is the single strongest Round 1 artefact — land on it with the actual correction row visible on screen, then cut immediately.
>
> **`[PRODUCTION]`** Read the live chunk count off the **Knowledge base** panel while recording and say that number. The written docs disagree between 918 and 1037 depending on when they were written; "about a thousand" is safe, the on-screen number is safer.

---

## §4 · The brief, and the two failures it names in us — 2:57 → 3:47 — **PARSHVA**

**`SCREEN`** **G4 — the commitment asymmetry card**. Left half first (the cost of one click). Right half of the card stays dimmed until §5.

**`SAY`**

> Our brief: show detail gradually, and detect conflicts before the user commits.
>
> When we went looking, our own product had exactly the two failures that sentence names.
>
> First — that Run button is a commitment. Eighty seconds. Metered tokens. A thirty-second lockout. No stop button.
>
> And our architecture is built so nothing ever fails: every source falls back to something. Which means every degradation was a log line nobody reads. If the detector replayed a stored answer instead of looking at imagery, the advisory came out looking exactly the same. The failure mode was never "it breaks". It was "it lies by omission".
>
> Second — we read four independent descriptions of the same storm, and validated each one alone. Nothing ever asked whether they agreed with each other.

**`ANCHOR`** A system built never to fail is a system that can never tell you it failed — and nobody was cross-checking the sources.

> **`[DIRECTION]`** *"It lies by omission"* is the second-strongest line in the pitch. Pause before it and after it. This is also the beat that proves we read the brief as an engineering problem rather than a feature request — the two halves of the brief map onto two real defects we found in our own product.

---

## §5 · LIVE DEMO — the gate — 3:47 → 5:17 — **TIRTH**

**`SCREEN`** Live console, full frame, nothing else. Storm `2024-10-G4` selected. Cursor visible.

**`SAY`**

> So this is the fix. Storm selected. Run clicked. And the first thing that happens is not the run.

**`SCREEN`** Click **Run live**. `[HOLD]` on the pre-flight panel for **four full seconds** in silence.

**`SAY`**

> Three layers. One sentence: *results will replay canned data, not this storm's imagery*. That is the consequence, not the fact — and the consequence is what decides the click.
>
> Next to it, the tally: one warn, three info, estimated seventy seconds.
>
> Behind one triangle, the complete evidence, nothing truncated.

**`SCREEN`** Expand `show all 4 findings`. Scroll once, slowly. Collapse.

**`SAY`**

> That check took three tenths of a second. Against an eighty-second commitment.
>
> Now watch what happens when I change storms.

**`SCREEN`** **Cancel.** Select `2024-05-G5`. Click **Run live**. Expand the findings. Highlight the fourth line with the cursor.

**`SAY`**

> Same findings — plus one more.
>
> Our reference for this storm says the CME left the Sun at twenty-two hundred kilometres per second. NASA's own analysis of the same event measured thirteen thirty-two. Sixty-five percent apart.
>
> Both files exist. Both parse. Neither is wrong on its own.
>
> And look at the severity. It's marked *info*, not *warn* — with a sentence appended saying detection is replaying a stub this run, so that file is never read, and the disagreement cannot reach the output.
>
> The panel is demoting its own finding.
>
> Cancel. Nothing ran. It never blocks.

**`SCREEN`** Click **Cancel**. Prior results are still on screen behind it. Hold two seconds.

**`ANCHOR`** Before it spends anything, the system tells you in one sentence what you are about to get — and it says something *different* for a different storm, so it is actually reading the data.

> **`[DIRECTION]`** The two-storm contrast is the whole demo. If a viewer only remembers one thing from the recording, it must be that the panel said something different the second time. A gate that says the same thing every run is a cookie banner, and everyone in the audience has already learned to click past those.
>
> **`[PRODUCTION]`**
> - Backend warm before recording — the health snapshot is warmed once at app startup, so a cold first click pays ~10 s that a warm one does not.
> - Have a completed run in a second tab so §9 has finished advisories to show without waiting 80 s on camera.
> - Browser zoom 110 %, 1920×1080, notifications off.
> - Do **not** click **Start run** in this beat. The point is that we did not commit.

---

## §6 · Deep dive I — the conflict engine and its tolerances — 5:17 → 6:17 — **PARSHVA**

**`SCREEN`** **G5 — the conflict rule card**. Build it: the two source panels first, then the tolerance gate, then the two verdicts (G4 silent, G5 fires), then the rule table underneath.

**`SAY`**

> That engine is what I want to open up, because it is the hard part.
>
> Validation asks one question: *is this number well-formed?* Every system does that. A conflict rule asks a different question: *can these two well-formed numbers both be true?* That needs two sources, and a physical tolerance — and the tolerance is where this is either engineering or theatre.
>
> So none of ours is a round number picked because it felt right.
>
> NASA publishes several independent analyses of the same CME, by different analysts, and those routinely spread ten to twenty percent. So our threshold is twenty-five. Below it, that is the method's own noise. Above it, the two files are not describing the same event.
>
> Ballistic arrival estimates carry about ten hours of error, so our arrival tolerance is twelve. A CME cannot arrive faster than it launched, so that bound is ten percent — measurement error, not an allowance.
>
> Six rules. Every threshold is a published error bar, plus headroom.

**`ANCHOR`** A conflict check is only as good as its tolerance, and every one of ours is derived from a measured error bar rather than chosen by taste.

**Technical backup for Q&A — the full rule catalogue:**

| Rule | Sources compared | Tolerance, and where it comes from |
|---|---|---|
| `stub_donki_speed_mismatch` | Committed reference vs NASA DONKI CME speed | **25 %** — DONKI's own independent analyses spread 10–20 % |
| `stub_donki_arrival_mismatch` | Reference arrival vs DONKI ballistic arrival | **12 h** — ballistic estimates carry ~10 h MAE |
| `speed_disagreement` | DONKI launch speed vs DSCOVR L1 wind speed | **+10 % / −70 %** — asymmetric because the physics is: drag decelerates, nothing accelerates a CME |
| `arrival_eta_mismatch` | DONKI ballistic arrival vs L1-implied ETA | **12 h** — same MAE |
| `bz_northward_strong_g` | Reference G-scale vs measured Bz sign | **No tolerance — a mechanism check.** Reconnection requires southward Bz; northward Bz behind a G3+ is a contradiction, not a discrepancy |
| `flare_r_mismatch` | Reference R-scale vs GOES XRS flare class | Two-tier: absent flare behind R2+ = `warn`; two or more R-levels apart = `info` |

**The line to have ready if asked "how do you know the check agrees with the run?":**

> Because it is the same code. The check calls the production parsers — `select_best_cme`, `fetch_and_classify_flare`, `fetch_l1_wind` — not lightweight copies. A prediction written against different code than the thing it predicts can disagree with it, and every one of those disagreements is a bug that only shows up in production.

> **`[DIRECTION]`** The "validation vs conflict" distinction in the first paragraph is the intellectual core of the submission. If you are running long, cut *anywhere else* before you cut that.

---

## §7 · Deep dive II — the observer effect — 6:17 → 7:07 — **PARSHVA**

**`SCREEN`** **G6 — the four traps card**. Reveal one quadrant per trap as it is named.

**`SAY`**

> And here is what actually made this hard.
>
> Adding an observer to a system is not read-only by default.
>
> Our data clients are cache-first-then-network — so "read this cache" really means "fetch it if it's missing". Checking naively would have created directories, called NOAA, and reported on data that did not exist until we looked.
>
> Our rate limiter is called `check`, and it *records* the call — so merely asking *may I run* would have consumed the run slot it was reporting on.
>
> Asking the model provider about quota spends the quota you are protecting.
>
> Four traps. Not one of them is a bug. Each is correct for its real caller, and wrong the moment a diagnostic becomes the caller.
>
> There is a test that points the entire check at an empty folder and asserts it is still empty.

**`ANCHOR`** Just *looking* at this system changes it — and getting that right, not writing the rules, was the actual work.

**The fourth trap** (on the card, only spoken if there is room, and the best answer to "what did you get wrong?"):

> The health probe. It loads six model checkpoints and counts every vector-store collection — and the vector store rewrites eleven tracked files on a pure read. Nine point seven seconds, and eleven dirty files, on every click of a button whose entire purpose was to save you eighty seconds. Fixed with a thirty-second TTL cache warmed once at startup: measured **9.7 s → 0.31 s**.
>
> And we fixed the *claim* as well as the behaviour. The docstring used to say the module never writes. That was false. It now scopes the promise precisely — read-only **for the storm caches**, not overall, and it names exactly which part is not covered. A comment that overstates a guarantee is worse than no comment: the next person trusts it and builds on a property that does not hold.

> **`[DIRECTION]`** This beat is aimed squarely at the most technical person watching. Deliver it flatter and faster than §6 — the content carries it. "Not one of them is a bug" is the pivot line; it reframes four bug-shaped things as a design insight.

---

## §8 · Deep dive III — relevance as a first-class output — 7:07 → 7:42 — **PARSHVA**

**`SCREEN`** **G7 — the relevance layer card**.

**`SAY`**

> One more mechanism, and it's the one I'd bet on.
>
> A conflict detector that reports every true contradiction becomes wallpaper. In hospitals, where most alarms are false, staff are documented to stop hearing them entirely.
>
> So relevance is a first-class output here. If a cached file is from the wrong month, we veto it — and withhold it from the physics rules, so we never dress a date error up as two instruments disagreeing. And if a finding is true but cannot reach this run's output, we demote it, visibly, and say why.
>
> Warn keeps meaning one thing: *this can change what you get.*

**`ANCHOR`** Reporting everything true is how warnings die. This one ranks its own findings by whether they can actually affect you.

**Backup detail for Q&A:**

- **The veto** (`_stale_epoch`) runs **last** in the cache pass, deliberately, so it can veto sources the rules would otherwise have consumed. When it fires it does two things: emits a `warn` explaining that the endpoint serves only recent data and cannot supply the requested date, **and sets the parsed value back to `None`** so no downstream rule can see it. It is the only rule in the module whose job is to *prevent other rules from producing findings*.
- **The demotion** drops `warn` → `info` and appends the reason to the finding's own detail text, so the demotion explains itself rather than reading as an inconsistency between the pill and the prose. Three options existed; we rejected two: leaving it `warn` erodes what `warn` means, and deleting it suppresses true information permanently.
- **Alarm-fatigue evidence:** clinical literature puts false-alarm rates at 72–99 %, and documents the resulting desensitisation as a patient-safety hazard in its own right. The design constraint is not aesthetic.

---

## §9 · The same principle, across the whole console — 7:42 → 8:12 — **TIRTH**

**`SCREEN`** Live console, the **completed run** from the second tab. Rapid cuts, roughly five seconds each: the rail with its badges → **Verifier** panel (proposed vs enforced table) → **Impact** panel (quantile band with the CI marker) → **Provenance** panel (a step rendered `not recorded`) → click a citation → the PDF opens **at the cited page**.

**`SAY`**

> And it isn't one panel. The same principle now runs the whole console.
>
> Ten layers, one panel at a time — the badge is the summary, the panel is the evidence.
>
> The verifier shows what the model proposed next to what the rules enforced.
>
> Every prediction shows its interval, not just its median.
>
> A missing provenance step renders as *missing*, not skipped.
>
> And a citation opens the actual regulation, at the actual page.
>
> Summary first. Evidence one deliberate click away. Everywhere.

**`ANCHOR`** This isn't a bolted-on panel — it is a design position applied consistently.

> **`[DIRECTION]`** The citation deep-link is the best five seconds of screen in the entire video. Make sure the PDF lands on the right page and the page number is legible. Do not narrate over the click — let the sound of the page opening carry it.

---

## §10 · The honest note — 8:12 → 8:37 — **PARSHVA**

**`SCREEN`** **G9 — the timeline card** (optional; a plain text card works). If skipping the graphic, cut back to Parshva on camera. This beat is stronger on a face than on a slide.

**`SAY`**

> One honest note, because it is the strongest thing we can tell you.
>
> Version one of this feature shipped green. Twenty-five passing tests. And on a clean clone, not one conflict rule could ever fire — the data they compared was never committed.
>
> The tests asked *does this compute correctly.* The review asked *does this ever run.*
>
> We found it in forty-seven minutes, and we documented it rather than deleting it.

**`ANCHOR`** They audit their own work, and they publish what they find.

**If asked to go further — volunteer this before it is found:**

| Limit | Statement |
|---|---|
| Coverage | Six rules exist; **one** can fire on a clean checkout. Four need L1/GOES caches that the upstream NOAA endpoints cannot serve for a historical date at all — they are real-time only and ignore the date parameter you send |
| Discriminating power | Two storms, and one signal separating them |
| Quota headroom | Process-local accounting. A second process on the same key is invisible, and the finding says so in its own text |
| Health staleness | Up to 30 s, by design — the alternative is 9.7 s and eleven rewritten files per click |
| A live one-line bug | `_stale_epoch` uses `abs(timedelta.days)`, which truncates toward negative infinity — so a 7.5-day gap fires in one direction and not the other. One-line fix, documented rather than quietly patched |

> **`[DIRECTION]`** Do not apologise here. Deliver it as a *capability claim* — the claim is that we review our own work adversarially and publish the result. That reads as maturity, and it pre-empts the hostile question by answering it first.

---

## §11 · Close — the pattern travels — 8:37 → 9:00 — **PARSHVA**

**`SCREEN`** **G8 — the portable pattern card**. Hold to black on the final line.

**`SAY`**

> So — what we are really claiming.
>
> Any system with expensive irreversible actions, several independent sensors, and graceful degradation has this exact blind spot. It cannot tell you it degraded, and it never checks its sources against each other.
>
> We built the answer for space weather because that is where the sources genuinely disagree, and the physics hands you tolerances you can defend.
>
> The pattern travels. That is what we would like to build next.

**`ANCHOR`** This is not a space-weather dashboard. It is a reusable safety mechanism that happens to have been proven on space weather.

> **`[DIRECTION]`** Land "The pattern travels" and stop. Do not add a thank-you, a team slide, or a URL over the top of it. Let the card hold for three seconds of silence, then fade.

---
---

# Graphic prompts

Nine prompts. Each is **self-contained** — paste one whole block into any image model (Midjourney, Imagen, DALL·E, Ideogram, Firefly, Nano Banana, Seedream) and it should produce the exact card without further context. Ideogram-class and Nano-Banana-class models handle dense text best; if your model garbles the small type, generate the layout and set the text in Figma/Canva over it.

**Shared style block.** It is already embedded in every prompt below, but keep it consistent if you regenerate anything:

> Dark technical-brief aesthetic for an aerospace operations deck. Background deep navy `#0E1220`, with a faint 40 px grid at 4 % opacity. Panels `#16213E` with 1 px `#2A3550` strokes. Accents: amber `#F39C12` = attention / the verifier, electric blue `#3498DB` = detection, green `#2ECC71` = safe / output, violet `#9B59B6` = generative, red `#E74C3C` = blocked / conflict, grey `#95A5A6` = inert / read-only. Type: geometric grotesque (Inter / Space Grotesk feel); ALL-CAPS wide-tracked labels for headers, sentence case for body. Flat vector, thin 1.5 px strokes. 16:9, 1920 × 1080, 96 px safe margins. No photorealism, no lens flare, no glowing "AI brain", no glossy 3D, no stock astronaut imagery.

---

## G1 — The vocabulary card

**Used at:** §1 (0:25–0:57). Held on screen ~32 s so viewers can pause and read.

```
A 16:9 reference card titled "BEFORE WE START — THE VOCABULARY", designed as a
dark technical-brief slide for an aerospace operations deck. 1920x1080.

LAYOUT
Header strip across the top: left-aligned ALL-CAPS title "BEFORE WE START — THE
VOCABULARY" in white, wide letter-spacing. Right-aligned small grey subtitle:
"pause here — 30 seconds". A thin 1px amber rule runs the full width beneath it.

Body is a 4-column x 4-row grid of 16 small panels, evenly spaced with 24px
gutters. Each panel is a rounded 4px rectangle, fill #16213E, 1px stroke
#2A3550, and contains exactly three text elements stacked:
  1) the SHORT FORM in large bold ALL-CAPS
  2) the FULL FORM in small ALL-CAPS grey letter-spaced type
  3) a one-line plain-English gloss in sentence case, light grey

The left two columns carry a 3px amber (#F39C12) left edge bar and belong to a
group labelled "SPACE WEATHER". The right two columns carry a 3px electric-blue
(#3498DB) left edge bar and belong to a group labelled "THE SYSTEM". These two
group labels sit as small vertical ALL-CAPS tabs on the far outer edges.

THE 16 PANELS, EXACT TEXT, IN READING ORDER

Row 1
  CME | CORONAL MASS EJECTION | A billion tonnes of magnetised plasma thrown off the Sun at 300-3000 km/s.
  G / S / R | NOAA SEVERITY SCALES 1-5 | Geomagnetic storm / radiation storm / radio blackout. 5 is the worst.
  CV | COMPUTER VISION | Reading the coronagraph frames. Here it is a threshold algorithm, not a neural net.
  RAG | RETRIEVAL-AUGMENTED GENERATION | A model that must answer from retrieved source text, and cite it.

Row 2
  Kp | PLANETARY K-INDEX | Global geomagnetic disturbance, 0 to 9. Kp 8.3 is a severe storm.
  Bz | INTERPLANETARY FIELD, N-S COMPONENT | Southward Bz drives storms. Northward Bz mostly does not.
  STUB | A STORED, REPLAYED ANSWER | What a system returns when it cannot compute a real one. Looks identical to real output.
  TPM | TOKENS PER MINUTE | How a language model is throttled. Exceeding it does not fail - it queues.

Row 3
  HF | HIGH FREQUENCY RADIO, 3-30 MHz | The only long-range voice link for aircraft over the poles.
  GIC | GEOMAGNETICALLY INDUCED CURRENT | Storm-driven current in long conductors. It heats grid transformers.
  CACHE | A LOCAL COPY OF REMOTE DATA | Read it from disk instead of the network. Missing? Most clients silently go fetch it.
  PRE-FLIGHT | A READ-ONLY DRY RUN | Describing what an action will do, without doing any of it.

Row 4
  L1 | LAGRANGE POINT 1 | ~1.5 million km sunward. Solar wind is measured there ~1 hour before it reaches Earth.
  DONKI | NASA CME DATABASE | Human-reviewed speed, width and arrival estimate. The only feed that serves historical dates.
  GOES / XRS | NOAA X-RAY SENSOR | Soft X-ray flux, mapped to flare class and the R-scale.
  DSCOVR | NASA SPACECRAFT AT L1 | Measures solar wind speed and Bz upstream of Earth.

Footer strip: a single centred line in amber italic, small:
"A conflict is two valid sources describing the same event in ways that cannot both be true."

STYLE
Background deep navy #0E1220 with a barely visible 40px grid at 4% opacity.
Panels #16213E, strokes #2A3550. Amber #F39C12, electric blue #3498DB, body text
#C9D2E3, gloss text #8A97AE. Geometric grotesque typeface (Inter / Space Grotesk
feel). Flat vector. Crisp, legible, high information density but generous
whitespace inside each panel.

DO NOT: no photorealism, no lens flare, no glowing brain or neural-network
imagery, no glossy 3D, no astronauts, no decorative planets. Render every string
of text exactly as written above, spelled correctly. Do not invent extra terms
or extra panels.
```

---

## G2 — The cost card

**Used at:** §2 (0:57–1:57). Three-stage reveal if your editor supports it.

```
A 16:9 dark infographic slide titled "THE COST OF A STORM NOBODY MISREAD",
designed as an aerospace operations brief. 1920x1080.

LAYOUT — three zones.

TOP-LEFT ZONE (55% width), labelled with a small ALL-CAPS amber tab reading
"ONE STORM · 10 MAY 2024 · LARGEST IN 20 YEARS". Inside, three stacked stat
rows, each a thin horizontal panel with a big figure on the left and a two-line
caption on the right:
  "$500M"  ->  "US Midwest corn. GPS-guided tractors stopped mid-field, in the
                middle of the planting window."
  "~50%"   ->  "of active satellites in low Earth orbit manoeuvred at once.
                Collision screening was effectively impossible for days."
  "6 FIGURES" -> "per unplanned polar flight reroute when HF radio goes down.
                  Sector-wide: EUR 0.21M-2.20M per day."

TOP-RIGHT ZONE (45% width), labelled with a small ALL-CAPS red tab reading
"THE TAIL". Two very large figures stacked, each with a one-line source caption
beneath in small grey type:
  "$2.4 TRILLION"     / "extreme space weather scenario, global — Lloyd's"
  "$41.5 BILLION/DAY" / "severe US blackout, domestic only — Cambridge Centre
                         for Risk Studies"
A faint red vertical hairline separates this zone from the left.

BOTTOM STRIP (full width, ~26% height), fill slightly lighter than the
background, with a 3px amber top edge. It contains a simple left-to-right
arrow diagram of five nodes connected by a single line:
  "SOLAR PHYSICS" -> "FORECAST MODELS" -> "ALERTS & SCALES" -> "THE LAST THIRTY
  SECONDS" -> "THE ACTION"
The first three nodes are drawn in solid electric blue with a small check glyph
and a tiny grey label under each reading "funded". The FOURTH node — "THE LAST
THIRTY SECONDS" — is drawn much larger, in amber, with a dashed outline and a
small label under it reading "unfunded". The fifth node is green.

Under the strip, one centred line of white text, larger than the labels:
"The warning is free. The response is not. Nobody instruments the moment of
commitment."

STYLE
Background deep navy #0E1220 with a faint 40px grid at 4% opacity. Panels
#16213E with 1px #2A3550 strokes. Big figures in white, extra bold, tabular
numerals. Amber #F39C12 for the gap, red #E74C3C for the tail, electric blue
#3498DB for the funded stages, green #2ECC71 for the action node. Body copy
#C9D2E3, captions #8A97AE. Geometric grotesque typeface. Flat vector, thin 1.5px
strokes, generous whitespace.

DO NOT: no photorealism, no stock imagery of the Sun or auroras, no lens flare,
no 3D bar charts, no glossy gradients. Render all figures and text exactly as
written. Keep the four dollar/percentage figures the single most visually
dominant elements on the slide.
```

---

## G3 — The architecture hero

**Used at:** §3 (1:57–2:57) under Tirth's sixty-second MVP recap. Also the slide to leave up during Q&A.

```
A 16:9 dark systems-architecture diagram titled "HELIOOPS — FIVE STAGES, ONE
DIRECTION", drawn as a clean aerospace engineering schematic. 1920x1080.

LAYOUT — a single left-to-right flow across the full width, five main stages
plus a source column at the far left and an output column at the far right.

FAR LEFT — a column labelled "SOURCES · FREE, PUBLIC, AUTHORITATIVE" containing
four small stacked chips:
  "CORONAGRAPH FITS · CCOR-1 / LASCO"
  "NASA DONKI · human-reviewed CME"
  "GOES XRS · flare class"
  "DSCOVR L1 · solar wind, Bz"
A single bundled line leaves this column and enters stage 1.

THE FIVE STAGES — five equal-width panels in a row, each with a large circled
number, an ALL-CAPS title, one bold descriptor line, and one italic output line
prefixed with an arrow. Each panel has a 3px coloured top edge:

  01  CV DETECTION      edge electric blue #3498DB
      "9-step threshold detector — no RNG, no trained weights"
      "-> StormEvent · G/S/R scales · byte-identical every run"

  02  ML IMPACT         edge green #2ECC71
      "6 LightGBM quantile models — q0.025 / q0.500 / q0.975"
      "-> GPS error ±95% CI · HF blackout ±95% CI"

  03  AGENTIC ADVISORY  edge violet #9B59B6
      "4 industry agents in parallel, RAG-grounded on the real rulebooks"
      "-> numbered actions · time window · cited source + page"

  04  DETERMINISTIC VERIFIER   edge red #E74C3C, and this panel's border is
      3px instead of 1px so it reads as the emphasised stage
      "ZERO-LLM RULE ENGINE — rewrites the unsafe value, does not merely flag it"
      "-> ICAO {3, 5, 8, 11, 17} MHz · GMDSS channels · NERC GIC steps"

  05  DELIVERY          edge amber #F39C12
      "FastAPI REST + WebSocket -> React operations console"
      "-> streamed live, persisted for audit"

Between stage 03 and stage 04, draw a small callout balloon in red pointing at
stage 04, containing two short lines:
  "agent proposes:  21 MHz"
  "engine enforces:  5 MHz"

FAR RIGHT — a single green output panel labelled "THE OPERATOR" containing:
"A numbered action list, with a time window, traceable to a page in a PDF."

BOTTOM BAND — a full-width thin band, dashed grey outline, fill slightly lighter
than the background, labelled on its left edge with an ALL-CAPS grey tab
"PRE-FLIGHT · READ-ONLY". Three short dashed grey arrows rise from this band up
into stages 01, 02 and 05, each arrow labelled in tiny grey type "inspects,
never mutates".

Under everything, one centred caption line in white:
"Deterministic where safety demands it. Generative only where language is
needed. A rule engine downstream of the model."

STYLE
Background deep navy #0E1220 with a faint 40px grid at 4% opacity. Panels
#16213E, 1px #2A3550 strokes. Connector lines 1.5px, light grey #5A6782, with
small arrowheads. Type: geometric grotesque, ALL-CAPS wide-tracked titles,
sentence-case body #C9D2E3, italic outputs #8A97AE. Flat vector schematic.

DO NOT: no photorealism, no 3D boxes with drop shadows, no clip-art icons of
satellites or robots, no lens flare, no rainbow gradients. Keep all connector
lines strictly horizontal or right-angled. Render all text exactly as written.
```

---

## G4 — The commitment asymmetry and the disclosure ladder

**Used at:** §4 (left half) and as a still under §5 if you need a cutaway.

```
A 16:9 dark two-panel slide titled "ASK BEFORE YOU SPEND", split by a vertical
1px amber rule down the exact centre. 1920x1080. Aerospace operations brief
aesthetic.

LEFT PANEL — header tab in red ALL-CAPS: "THE COST OF ONE CLICK".
A large amber-outlined button graphic labelled "RUN" sits at the top, and four
cost rows run beneath it, each a thin panel with an icon-free bold figure on the
left and a caption on the right:
  "65-80 s"   "wall time — four parallel LLM reasoning passes"
  "METERED"   "tokens spent against a fixed per-minute budget"
  "30 s"      "lockout — the second press is refused with a 429"
  "NONE"      "reversibility — in the MVP there was no stop control"
Beneath the rows, one line in red: "Irreversible for at least the next half
minute."

RIGHT PANEL — header tab in green ALL-CAPS: "THE COST OF ASKING FIRST".
A single very large figure at the top: "0.31 s" with a small caption "measured,
warm". Under it, three short rows:
  "NO QUOTA SPENT"
  "NO CACHE WRITES, NO NETWORK CALLS"
  "NO RUN SLOT CONSUMED"

Between the two panels, straddling the centre rule at mid-height, place a
circular amber badge containing large text "~260x" and, beneath it in small
white type, "cheaper to ask than to commit".

BOTTOM THIRD — full width, spanning both panels, a horizontal three-step ladder
labelled with a small white ALL-CAPS tab "WHAT THE OPERATOR IS SHOWN, IN ORDER".
Three stacked bands, each wider and lighter than the one below, drawn as a
staircase descending left to right:

  LAYER 1 — DECIDE   (largest type, amber)
      "Results will replay canned data, not this storm's imagery."
      small grey note: "one sentence. The consequence, not the fact."

  LAYER 1b — SCAN    (medium)
      three small pill shapes reading  "1 warn"   "3 info"   "est ~70s"
      small grey note: "the tally, beside the sentence — never instead of it."

  LAYER 2 — EVIDENCE (smallest, collapsed)
      a disclosure-triangle glyph followed by "show all 4 findings"
      small grey note: "full physics, nothing truncated, one deliberate click away."

STYLE
Background deep navy #0E1220 with a faint 40px grid at 4% opacity. Panels
#16213E, 1px #2A3550 strokes. Red #E74C3C for cost, green #2ECC71 for the cheap
check, amber #F39C12 for the ratio badge and the decide layer. Body #C9D2E3,
notes #8A97AE. Geometric grotesque type, tabular numerals for figures. Flat
vector.

DO NOT: no photorealism, no glossy 3D buttons, no drop shadows, no stopwatch or
money clip-art, no gradients other than flat fills. Render all text exactly as
written, including "~260x" and "0.31 s".
```

---

## G5 — The conflict rule card

**Used at:** §6 (5:17–6:17). The most important technical graphic in the deck.

```
A 16:9 dark technical diagram titled "A CONFLICT RULE IS NOT A VALIDATION RULE",
1920x1080, aerospace engineering brief aesthetic.

TOP BAND — two contrasting statements side by side, separated by a vertical
hairline:
  LEFT, in grey:  "VALIDATION ASKS"  /  "Is this number well-formed?"  /
                  "one source · every system does this"
  RIGHT, in amber: "A CONFLICT RULE ASKS"  /  "Can these two well-formed numbers
                  both be true?"  /  "two sources + a physical tolerance"

MIDDLE — THE MECHANISM, drawn as a left-to-right flow occupying the central 45%
of the slide height.
Two source panels on the left, stacked vertically, each with a small ALL-CAPS
label and a large number:
  "COMMITTED REFERENCE"  ->  "2200 km/s"
  "NASA DONKI ANALYSIS"  ->  "1332 km/s"
Both feed with 1.5px lines into a hexagonal gate in the centre labelled across
two lines:
  "TOLERANCE GATE"
  "25%  —  DONKI's own analyses spread 10-20%"
From the gate, two labelled outputs diverge:
  UPPER, green, small: "within spread -> SILENT"
  LOWER, red, bold:    "65.2% apart -> FIRES"
The lower output leads to a finding card drawn as a small panel with an amber
"info" pill, the title "Reference CME speed is 65% off the DONKI record", and
one line of body text.

Directly beneath the mechanism, a slim two-row comparison strip proving the two
storms differ:
  "2024-10-G4   ref 1480 km/s   vs   DONKI 1323 km/s   =  11.9%   ->  SILENT"  (green)
  "2024-05-G5   ref 2200 km/s   vs   DONKI 1332 km/s   =  65.2%   ->  FIRES"   (red)
With a small amber caption to the right: "The two storms say different things.
That is what stops the panel becoming a cookie banner."

BOTTOM BAND — a compact 6-row table, header row in ALL-CAPS grey:
"RULE | COMPARES | TOLERANCE, AND WHERE IT COMES FROM"
  stub_donki_speed_mismatch   | reference vs DONKI speed        | 25% — DONKI analyses spread 10-20%
  stub_donki_arrival_mismatch | reference vs ballistic arrival  | 12 h — ballistic estimates carry ~10 h MAE
  speed_disagreement          | DONKI launch vs L1 wind speed   | +10% / -70% — drag decelerates, nothing accelerates
  arrival_eta_mismatch        | ballistic vs L1-implied arrival | 12 h — same MAE
  bz_northward_strong_g       | G-scale vs measured Bz sign     | no tolerance — reconnection requires southward Bz
  flare_r_mismatch            | R-scale vs GOES flare class     | absent flare behind R2+ = warn
Rule names are rendered in a monospace typeface; the rest in the sans face.

STYLE
Background deep navy #0E1220 with a faint 40px grid at 4% opacity. Panels
#16213E, 1px #2A3550 strokes. Amber #F39C12 for the conflict framing and the
gate, green #2ECC71 for silent, red #E74C3C for fires, grey #8A97AE for
validation and captions. Numbers in tabular figures, large and bold. Geometric
grotesque sans plus a clean monospace for identifiers. Flat vector schematic,
right-angled connectors.

DO NOT: no photorealism, no 3D, no drop shadows, no clip-art of the Sun or
satellites, no decorative particles. Render every number and rule name exactly
as written — 2200, 1332, 65.2%, 1480, 1323, 11.9%, 25%, 12 h, +10% / -70%.
```

---

## G6 — The observer effect: four traps

**Used at:** §7 (6:17–7:07). Reveal one quadrant per trap.

```
A 16:9 dark engineering slide titled "ADDING AN OBSERVER IS NOT READ-ONLY BY
DEFAULT", subtitled in small grey type "four components that were correct — and
became traps the moment a diagnostic became the caller". 1920x1080.

LAYOUT — a 2x2 grid of four large quadrant panels, generous 32px gutters. Each
quadrant has a 3px red top edge and contains four labelled text blocks stacked,
each block preceded by a small ALL-CAPS grey key:

  COMPONENT   (bold white, large)
  CORRECT FOR (one line, grey)
  THE TRAP    (two lines, red)
  THE FIX     (one line, green)

QUADRANT 1 — top left
  COMPONENT: "Cache-first data clients"
  CORRECT FOR: "the pipeline, which wants the data no matter what"
  THE TRAP: "'read this cache' means 'fetch it if missing'. It mkdirs on entry.
             Checking naively creates directories, calls NOAA, and reports on
             data that did not exist until you looked."
  THE FIX: "stat the file first. Parse only if it already exists. Absence is a
            finding, never a fetch."

QUADRANT 2 — top right
  COMPONENT: "check_rate_limit()"
  CORRECT FOR: "POST /api/detect, which asks once and is about to run"
  THE TRAP: "the function named 'check' RECORDS the call it checks. Asking
             'may I run?' consumes the run slot you are reporting on. The user
             is told yes, presses start, and gets a 429."
  THE FIX: "peek_rate_limit() — a non-mutating twin that returns the wait in
            seconds instead of a boolean."

QUADRANT 3 — bottom left
  COMPONENT: "Model provider quota API"
  CORRECT FOR: "a client that intends to spend quota"
  THE TRAP: "asking 'is there budget left?' spends budget — on every click of
             the button that exists to protect it. A check that consumes the
             resource it protects is a leak with a user interface."
  THE FIX: "read this process's own token accounting, and state the limitation
            in the finding itself."

QUADRANT 4 — bottom right
  COMPONENT: "health_collector.run()"
  CORRECT FOR: "a /health endpoint, called rarely"
  THE TRAP: "loads six model checkpoints and counts every vector-store
             collection — and the store rewrites 11 tracked files on a PURE
             READ. 9.7 s and 11 dirty files per click."
  THE FIX: "30 s TTL cache, warmed once at startup. Measured 9.7 s -> 0.31 s."

BOTTOM STRIP — full width, amber 3px top edge, containing two lines centred:
Line 1, larger, white: "Not one of these is a bug."
Line 2, grey: "Each is correct for its intended caller, and wrong the moment a
diagnostic becomes the caller."

Bottom-right corner, a small green-outlined chip containing monospace text:
"assert not any(tmp_path.rglob('*'))"
and beneath it in tiny grey type: "the whole check, pointed at an empty
directory. It stays empty."

STYLE
Background deep navy #0E1220 with a faint 40px grid at 4% opacity. Quadrant
panels #16213E, 1px #2A3550 strokes. Red #E74C3C for traps, green #2ECC71 for
fixes, grey #8A97AE for the 'correct for' line, amber #F39C12 for the bottom
strip. Component names and the code chip in monospace; everything else
geometric grotesque sans. Flat vector.

DO NOT: no photorealism, no thermometer/microscope metaphor illustrations, no
3D, no drop shadows, no emoji. Render all code identifiers and the numbers
9.7 s, 0.31 s, 11, 429 and 30 s exactly as written.
```

---

## G7 — The relevance layer

**Used at:** §8 (7:07–7:42).

```
A 16:9 dark slide titled "REPORTING EVERYTHING TRUE IS HOW WARNINGS DIE",
subtitled in small grey "relevance is an output, not an afterthought".
1920x1080. Aerospace operations brief aesthetic.

LEFT COLUMN (32% width) — a vertical "evidence" strip with a red 3px left edge,
headed "THE FAILURE MODE" in ALL-CAPS. It contains one large figure and two
short lines:
  "72-99%"
  "of clinical alarms are false"
  "Documented consequence: staff stop hearing them. Alarm fatigue is a
   patient-safety hazard in its own right."
Beneath, a small grey line: "Any detector that reports every true contradiction
converges on this."

RIGHT AREA (68% width) — two stacked mechanism panels, each drawn as a small
left-to-right flow.

PANEL A, headed "MECHANISM 1 — THE VETO" with an amber tab reading
"_stale_epoch · runs LAST, on purpose":
  A source chip labelled "DSCOVR L1 cache · file named 2024-10-10" flows into a
  diamond decision labelled "does this file's epoch match the storm?" -> "NO,
  87 days off".
  Two outputs leave the diamond:
    output 1, amber: "EMIT a warn — the endpoint is real-time only and ignores
                      the date you ask for"
    output 2, red and bold, drawn with a thick strike-through symbol on the
             onward line: "SET THE PARSED VALUE BACK TO None — withhold this
             source from every physics rule"
  A caption underneath in white: "Otherwise every rule fires, every finding is
  true, and every one of them is useless — a date-range error dressed up as two
  instruments disagreeing."

PANEL B, headed "MECHANISM 2 — THE DEMOTION" with an amber tab reading
"stub replay · the finding is true but cannot reach the output":
  A finding card on the left showing an amber pill "warn" and the title
  "Reference CME speed is 65% off the DONKI record".
  An arrow labelled "detection is replaying a stub — this file is never read"
  leads to the same card on the right, now showing a grey pill "info", the same
  title, and one appended italic sentence highlighted in amber:
  "Detection is replaying the stub for this run, so this source is never read
   and the disagreement cannot affect the output."
  Below, three small options in a row, two struck through in red and one ticked
  in green:
    struck: "leave it warn — erodes what warn means"
    struck: "delete it — suppresses true information, permanently"
    ticked: "demote it, visibly, and append the reason"

BOTTOM STRIP — full width, green 3px top edge, one centred line in white, large:
"So 'warn' keeps meaning exactly one thing: this can change what you get."

STYLE
Background deep navy #0E1220 with a faint 40px grid at 4% opacity. Panels
#16213E, 1px #2A3550 strokes. Red #E74C3C for the failure mode and rejected
options, amber #F39C12 for the mechanisms and the appended sentence, grey
#8A97AE for demoted state, green #2ECC71 for the chosen option and the bottom
strip. Identifiers (_stale_epoch, None) in monospace. Everything else geometric
grotesque sans. Flat vector, right-angled connectors.

DO NOT: no photorealism, no hospital or siren imagery, no 3D, no drop shadows,
no emoji. Render "72-99%", "None", "_stale_epoch", "warn", "info" and the
appended sentence exactly as written.
```

---

## G8 — The portable pattern (closing card)

**Used at:** §11 (8:37–9:00). Holds to black.

```
A 16:9 dark closing slide titled "THE PATTERN TRAVELS", 1920x1080, aerospace
operations brief aesthetic. Calm, spacious, fewer elements than the other cards.

TOP THIRD — a horizontal row of three "precondition" chips, each an outlined
rounded rectangle with an ALL-CAPS label and a one-line gloss, joined by two
small plus signs between them, and an equals sign after the third:

  "EXPENSIVE, IRREVERSIBLE ACTIONS"
     "committing costs money, time, or a lockout you cannot undo"
   +
  "SEVERAL INDEPENDENT SENSORS"
     "more than one source describes the same event"
   +
  "GRACEFUL DEGRADATION"
     "nothing hard-fails, so nothing announces that it failed"
   =
  a single amber-filled panel reading "THIS EXACT BLIND SPOT"
     "it cannot tell you it degraded, and it never checks its sources against
      each other"

MIDDLE THIRD — a horizontal four-step mechanism bar, each step a panel with an
ALL-CAPS title and one line beneath, connected by thin arrows:
  "READ WITHOUT RUNNING"   "a dry run that never mutates the state it describes"
  "COMPARE THE SOURCES"    "physical tolerances from published error bars, not taste"
  "RANK BY REACHABILITY"   "veto invalid inputs, demote findings that cannot affect the output"
  "DISCLOSE IN LAYERS"     "one consequence sentence, then the tally, then the evidence"

BOTTOM THIRD — a row of four small domain cards under a small grey ALL-CAPS
label "WHERE IT TRANSFERS", each with a title and one line:
  "MISSION OPERATIONS"  "go / no-go on telemetry that disagrees"
  "LAUNCH & RANGE"      "commit windows measured in minutes, sensors measured in dozens"
  "AUTONOMOUS SYSTEMS"  "sensor fusion that fails soft and reports nothing"
  "CLINICAL DECISION SUPPORT" "irreversible orders, contradictory monitors, alarm fatigue"

FOOTER — one centred line, white, larger than everything else on the bottom
third, with generous space above and below:
"We built it for space weather because that is where the sources genuinely
disagree — and the physics hands you tolerances you can defend."

STYLE
Background deep navy #0E1220 with a faint 40px grid at 4% opacity, and a very
subtle radial amber glow at 6% opacity behind the top-third amber panel only.
Panels #16213E, 1px #2A3550 strokes. Amber #F39C12 for the blind-spot panel,
electric blue #3498DB for the mechanism bar, grey #8A97AE for the domain cards.
Geometric grotesque sans throughout. Flat vector. Noticeably more negative space
than the other slides — this one should feel like an exhale.

DO NOT: no photorealism, no logos, no team photos, no contact details, no
call-to-action button, no lens flare, no 3D. Render all text exactly as written.
```

---

## G9 — The timeline card *(optional, §10)*

Only generate this if you decide §10 plays better on a slide than on Parshva's face. On balance: **use the face.**

```
A 16:9 dark slide titled "WHAT THE SHAPE OF THIS TIMELINE SAYS", 1920x1080,
aerospace engineering brief aesthetic.

LAYOUT — a single horizontal timeline rail across the middle of the slide, with
five nodes at uneven spacing reflecting real elapsed time. Each node has a time
label above the rail and a description panel below it. One node is deliberately
larger than the others.

  15:47  "THE PLAN"
         "155 lines. Schema, findings catalogue, conflict rules with their
          tolerances — and all three read-only constraints identified BEFORE any
          code existed."

  16:06  "VERSION ONE SHIPS"
         "~317 lines. 270 tests, 25 new. Ruff clean. Verified live. Every claim
          in the commit message true."

  ~16:10 "THE REVIEW"   — drawn in amber, with a magnifier-free callout balloon
         containing one question in large type:
         "What does this return on a machine that has just cloned the repo?"
         and beneath it, in red: "Answer: the same four findings. Both storms.
         Forever. Every conflict rule unreachable."

  16:53  "THE FIX"      — the LARGEST node, red 3px edge
         "+1581 / -42 across 11 files. Reference data committed, stale-epoch
          veto added, demotion added, a false docstring corrected and the 9.7 s
          behind it removed, disclosure rebuilt. 284 tests."

  17:42  "CLOSED"
         "66 minutes, plan to corrected feature."

BOTTOM STRIP — full width, amber 3px top edge, two centred lines:
Line 1, white, large: "Two commits, 47 minutes apart — and the second is larger
than the first."
Line 2, grey: "The tests asked 'does this compute correctly?'. The review asked
'does this ever run?'. Both are necessary. Only one was automated."

STYLE
Background deep navy #0E1220 with a faint 40px grid at 4% opacity. Rail 2px
#5A6782 with circular nodes. Panels #16213E, 1px #2A3550 strokes. Amber #F39C12
for the review node, red #E74C3C for the fix node and the failure line, green
#2ECC71 for the closed node. Times in tabular monospace figures. Geometric
grotesque sans for body. Flat vector.

DO NOT: no photorealism, no 3D, no clock or calendar clip-art, no drop shadows.
Render all timestamps and numbers exactly as written.
```

---
---

# Delivery kit

## Cut lists

The base script lands at **8:45–8:55**. If you must come in shorter, cut in this order — each cut is designed to remove a whole idea, never to speed up delivery.

**To reach ~8:00 (cut 0:50)**

| Cut | Saves | Cost |
|---|---|---|
| §9 down to three lines: rail / verifier / citation deep-link only | 0:15 | Loses the breadth argument, keeps the strongest visual |
| §2 — drop the LEO satellite sentence | 0:10 | You keep two of three impact vectors |
| §6 — drop the ballistic-arrival paragraph, keep the DONKI-spread one | 0:15 | One worked example instead of two; the principle survives |
| §7 — drop the quota-probe trap, keep three | 0:10 | Three traps still make the point |

**To reach ~7:15 (cut a further 0:45)**

| Cut | Saves | Cost |
|---|---|---|
| §3 down to 40 s — name the five stages, keep only the 21 MHz correction | 0:20 | Acceptable; §3 is context, not content |
| §10 down to the two middle lines | 0:12 | Keeps "the tests asked / the review asked", loses the setup |
| §1 — read four terms instead of six, hold the card the same length | 0:13 | The card still does the work |

**Never cut:** the two-storm contrast in §5, the validation-vs-conflict distinction in §6, and the final two lines of §11.

---

## Rehearsal checklist

- [ ] Both presenters have run their own sections aloud against a stopwatch, twice.
- [ ] Parshva has read §0 with the one-second pause before "The decisions didn't."
- [ ] Tirth has clicked the §5 sequence end to end at least three times, so the two-storm switch is muscle memory and the cursor never hunts.
- [ ] The handoffs are rehearsed. Three of them: Parshva→Tirth at 1:57, Tirth→Parshva at 5:17, Parshva→Tirth at 7:42 and back at 8:12. A visible half-second gap at a handoff reads as a mistake; record them as one take each if possible.
- [ ] All eight graphics generated, text proofread on screen at 100 % zoom. Image models mangle small type — check `0.31 s`, `65.2%`, `1332`, `9.7 s`, `72-99%` character by character.

## Recording checklist

- [ ] Backend up and **warm** — the health snapshot warms at startup; a cold first pre-flight click pays ~10 s that a warm one does not, and that would contradict the "three tenths of a second" claim on screen.
- [ ] A completed run sitting in a second browser tab for §3 and §9.
- [ ] Browser at 1920 × 1080, zoom 110 %, all notifications off, bookmark bar hidden.
- [ ] The cited PDF **closed** before recording — §9 opens it from inside the product, and that is the point.
- [ ] Read the live chunk count off the Knowledge base panel before you narrate §3.
- [ ] Record system audio separately from voice if you can; the console has no sound, so this mostly means a clean voice track you can re-time against the cuts.

---

## The seven questions to be ready for

Short, direct answers. Say the answer first, then the reason.

**"Is this just a confirmation dialog?"**
> No. A confirmation dialog restates the action. This restates the *consequence*, computed from the actual state of the actual data — and it says something different for a different storm. The dialog you are thinking of would say the same thing every time, which is exactly the failure mode we designed against.

**"Why not just block the run when there is a conflict?"**
> Two reasons. Product: a gate that fails closed means a bug in a diagnostic can cost you the whole session — a diagnostic that can break the thing it diagnoses is worse than no diagnostic. Principle: the operator has context the check does not. "Rate limited, wait 22 seconds" is information; deciding on their behalf that they may not proceed is presumption, not safety.

**"How do you know your check agrees with the pipeline?"**
> Because it is the same code — the check calls the production parsers, not lightweight copies. A predictor written against different code than the thing it predicts can disagree with it, and every one of those disagreements is a bug that only appears in production.

**"How many rules actually fire in practice?"**
> On a clean checkout, one — and we say so in our own documentation before anyone asks. Four of the six need solar-wind and X-ray caches that the upstream endpoints cannot serve for a historical date at all; they are real-time only and ignore the date parameter. That constraint is reported honestly by a stale-epoch rule rather than papered over, and finding it also explained a pre-existing bug: our flare classifier was reporting C-class for two X-class storms, because it was searching a file from the wrong month.

**"Is any of this novel, or is it good UI?"**
> The disclosure ladder is good UI, and we would not claim more. The two things we would defend as novel in this setting are the *relevance layer* — a detector that vetoes its own inputs and demotes its own findings by whether they can reach the output — and the *read-only observation guarantee* in a codebase where four separate components write on read. Neither is a model. Both are the reason the panel is still worth reading on the fiftieth run.

**"Twenty-four hours is not much. How much of this is real?"**
> The feature is one new module, one route, one component, one pure function, no new dependency, no pipeline change and no schema change — delete it and the product reverts exactly. That clean seam is what "substantial without a rebuild" actually asks for. It carries 35 tests of its own inside a 308-test backend suite, and one of those tests points the entire check at an empty directory and asserts it is still empty.

**"What would you build next?"**
> Thread the pre-flight findings *into* the run, so the advisory that comes out is annotated with the degradations that were predicted before it started. Today the panel's knowledge is discarded the moment you press Start. That was an explicit, recorded scope decision, not an oversight.

---

## Fact sheet — every number spoken on camera

Check each one against the working tree before recording. If a number has moved, change the script, not the number.

| Spoken | Value | Where it comes from |
|---|---|---|
| Pre-flight duration | **0.31 s** measured, warm | `docs/preflight/04-how-it-works.md` §4.8 |
| Pipeline duration | **65–80 s** | `README.md`, measured |
| Lockout | **30 s** per storm | `backend/middleware.py` |
| G5 reference speed | **2200 km/s** | `backend/cv/stubs/storm_event_2024-05-G5.json` |
| G5 DONKI speed | **1332 km/s** | `backend/data/cached/donki/cme_2024-05-*.json` |
| G5 drift | **65.2 %** | computed, fires against the 25 % tolerance |
| G4 drift | **11.9 %** (1480 vs 1323 km/s) | computed, stays silent |
| Speed tolerance | **25 %** | DONKI analyses spread 10–20 % |
| Arrival tolerance | **12 h** | ballistic estimates carry ~10 h MAE |
| Conflict rules | **6** in the module, **1** fires on a clean checkout | `backend/preflight.py` |
| Health probe cost | **9.7 s → 0.31 s**, 11 tracked files | `docs/preflight/06-*.md` §6.5 |
| Pre-flight tests | **35** across 8 classes | `backend/tests/test_preflight.py` |
| Backend suite | **308 passing** | measured 2026-08-23 |
| Fix commit size | **+1581 / −42** across 11 files | `git show --stat a18490b` |
| Plan → corrected feature | **66 min**; two commits **47 min** apart | `docs/preflight/10-timeline.md` |
| Knowledge base | read the live count off the console | docs disagree, 918 vs 1037 |
| ICAO NAT HF set | **{3, 5, 8, 11, 17} MHz** | `backend/genai/verifier.py` |

---

## Reference material behind this script

| Document | What it holds |
|---|---|
| `docs/PS_solution/main_features.md` | The full Round 2 feature specification, Tier A and Tier B, with `file:line` for every claim |
| `docs/preflight/` | Thirteen files, ~2160 lines — the complete feature record including chapter 7, what shipped broken |
| `docs/preflight/05-the-conflict-rules.md` | The physics behind every tolerance |
| `docs/preflight/06-the-read-only-invariants.md` | The four observer-effect traps in full |
| `docs/preflight/11-open-issues.md` | Every known limit, volunteered |
| `docs/ARCHITECTURE_DIAGRAM.md` | Source mermaid for G3 and the verifier detail diagram |
| `README.md` | The whole system, and the maturity statement |
