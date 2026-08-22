# HelioOps Dashboard — Feature Inventory and Gap Analysis

**Scope:** the operator-facing SPA in `frontend/` — primarily the Advisory Console
(`/dashboard`), plus the surrounding four-page site.

**Method:** every entry below was read out of the source, not inferred from
commit messages. Feature claims cite `file:line`. Gap claims were verified
against the running contract (backend route list, `PipelineResult` schema, the
committed stubs, and what is actually on disk).

**Verified against:** `frontend/src/` at `9b19b85`, `backend/app.py` route table,
`backend/pipeline.py:44` (`PipelineResult`), `backend/cv/stubs/*.json`.

---

# PART 1 — WHAT THE DASHBOARD DOES

## A. Run control and the pre-flight gate

The headline Round 2 capability. Every run passes through a gate before the
65–80s commitment.

| # | Feature | Where |
|---|---|---|
| A1 | **Storm selector** — populated live from `GET /api/storms`, disabled while busy or gated | `Dashboard.jsx:454-468` |
| A2 | **Two run modes** — `Run live (WebSocket)` streams events; `Run batch (REST)` posts and waits | `Dashboard.jsx:470-483` |
| A3 | **Pre-flight gate on both runners** — neither can bypass it; the chosen runner is carried through the gate state | `Dashboard.jsx:410-436` |
| A4 | **Layer 1 — the headline sentence.** One plain-English line taken from the most severe finding, describing the *consequence*, colour-coded by severity | `Dashboard.jsx:298` |
| A5 | **Layer 1b — severity pills + duration estimate.** `1 warn`, `3 info`, `est ~70s` — the scan layer, next to the sentence rather than instead of it | `Dashboard.jsx:286-295` |
| A6 | **Layer 2 — full evidence behind `<details>`.** Every finding with severity pill, title, and untruncated physics detail | `Dashboard.jsx:309-324` |
| A7 | **Clean-state handling** — renders a `clear` pill and a "nothing to flag" headline rather than vanishing | `Dashboard.jsx:294`, `preflight.js` |
| A8 | **One button label.** `Start run` / `Cancel`. Never two labels for one behaviour | `Dashboard.jsx:300-307` |
| A9 | **Never hard-blocks.** Even a `block` finding leaves `Start run` enabled | `Dashboard.jsx:301` |
| A10 | **Fail-open.** If pre-flight itself throws, the gate disappears and the run starts as if the feature did not exist | `Dashboard.jsx:424-427` |
| A11 | **Pure decision layer.** `gateDecision()` — severity sort, headline selection, counts — isolated in its own module and asserted by plain node asserts | `preflight.js:1-47`, `data.test.mjs` |
| A12 | **Unknown severities sort last**, not first, so a future 4th severity can never hijack the headline | `preflight.js` (`rank()`) |
| A13 | **Cancel is non-destructive** — removes the panel, starts nothing, keeps prior results on screen | `Dashboard.jsx:500` |

## B. Live pipeline stream

| # | Feature | Where |
|---|---|---|
| B1 | **WebSocket event stream** — `pipeline.stage`, `agent.thinking`, `advisory.generated`, `verifier.check`, `advisory.verified`, `pipeline.complete` | `api.js:60-84` |
| B2 | **Three-column event rows** — tag (industry/stage), step, message | `Dashboard.jsx:105-111` |
| B3 | **Structured event rendering.** Events without a `message` are *composed*, not blanked — a blocked verifier check renders `field: 21 REJECTED → corrected to 5` | `Dashboard.jsx:68-83` |
| B4 | **Semantic colour-coding** — errors red, blocked checks red, passed checks green, generation/completion green | `Dashboard.jsx:85-91` |
| B5 | **Auto-scroll to newest event** via `scrollIntoView({block:'nearest'})` | `Dashboard.jsx:94-97` |
| B6 | **Empty state with instruction** rather than a blank panel | `Dashboard.jsx:99-101` |
| B7 | **Socket cleanup on unmount** and on re-run — no leaked connections | `Dashboard.jsx:362, 370` |
| B8 | **Post-stream result fetch.** The stream carries advisories; the persisted result additionally carries verifier output, so it re-fetches on close | `Dashboard.jsx:376-381` |

## C. Advisory rendering

| # | Feature | Where |
|---|---|---|
| C1 | **Collapsible per-industry cards**, open by default | `Dashboard.jsx:149-158` |
| C2 | **Severity pill** with a 5-level order map (CRITICAL/HIGH/MEDIUM/LOW/NONE) | `Dashboard.jsx:24, 161-163` |
| C3 | **Confidence bar** — visual, three-tone (≥0.75 ok, ≥0.5 warn, below bad), with numeric readout | `Dashboard.jsx:53-60` |
| C4 | **Numbered action list** — action text, time window, citation, and rationale per step | `Dashboard.jsx:194-205` |
| C5 | **Guardrail safety flags** with per-flag tone mapping (`HALLUCINATION_DETECTED`, `CITATION_GAP`, `SEVERITY_MISMATCH`, `LOW_CONFIDENCE`, `LOW_COVERAGE`, `GENERATION_FAILED`) | `Dashboard.jsx:27-34, 176-185` |
| C6 | **Explicit "no guardrail flags" pill** — absence is stated, not implied by emptiness | `Dashboard.jsx:177-178` |
| C7 | **Generation notes** collapsed behind `<details>` when the run had non-fatal issues | `Dashboard.jsx:227-240` |
| C8 | **Sources-cited footer** per advisory | `Dashboard.jsx:242-244` |
| C9 | **Pipeline-level error banner** — `result.errors` surfaced as a warn banner, separate from fatal errors | `Dashboard.jsx:530-534` |

## D. Deterministic verifier surface

The part no competing product has, and the console gives it dedicated real
estate.

| # | Feature | Where |
|---|---|---|
| D1 | **Verifier status pill** — `passed` / `passed_with_corrections` / `blocked` / `not_applicable`, each with its own tone | `Dashboard.jsx:36-41, 186-190` |
| D2 | **"Requires human review" pill** when the verifier escalates | `Dashboard.jsx:191` |
| D3 | **Corrections box** — for every blocked check, shows `field`, what the model **proposed**, what it was **corrected to**, and the reason. The operator sees both sides | `Dashboard.jsx:207-218` |
| D4 | **Passed-checks summary** — when nothing was corrected, names which fields were checked, so silence is legible as "checked and fine" rather than "not checked" | `Dashboard.jsx:220-225` |
| D5 | **Blocked checks also surface live in the stream** as they happen, not only in the final card | `Dashboard.jsx:71-73` |

## E. Citations

| # | Feature | Where |
|---|---|---|
| E1 | **Deep-link to the source PDF at the cited page** — `source_ref` becomes an anchor with `#page=N`, honoured natively by Chrome and Firefox | `Dashboard.jsx:125-146`, `citation.js` |
| E2 | **No new dependency** — no PDF.js; uses the browser's own viewer | `citation.js` |
| E3 | **Graceful non-link fallback.** A ref naming no document (a bare regulation code) stays plain text rather than becoming a dead link | `Dashboard.jsx:128-134` |
| E4 | **Parsing isolated for testability** — `citationPath()` lives outside `api.js` so the node runner can reach it without vite's `import.meta.env` | `citation.js`, `api.js:33-37` |
| E5 | **Path-traversal safe.** The filename is only ever a key into a startup-globbed allowlist, so no `../` resolves | `backend/app.py:245-263` |
| E6 | **Chat answers reuse the same component**, so a citation in a chat reply deep-links identically | `Dashboard.jsx:251`, `AskBox.jsx:65` |

## F. Operator chat (per-agent, scoped)

| # | Feature | Where |
|---|---|---|
| F1 | **Scoped to one industry agent and one advisory** — inherits both from the card, so it never asks "which agent?" | `AskBox.jsx:12, 25` |
| F2 | **Lives in a collapsed `<details>` at the card foot** — zero additional chrome | `AskBox.jsx:51-52` |
| F3 | **Separate Groq TPM bucket.** Runs on the checker model, so chatting can never starve a pipeline run of its budget | `api.js:48-56`, `backend/genai/ask.py` |
| F4 | **Enter sends, Shift+Enter newlines** — the convention every chat input uses | `AskBox.jsx:43-48` |
| F5 | **Per-card in-memory history** with Q/A/sources per turn | `AskBox.jsx:54-73` |
| F6 | **Thinking state** — "The {industry} agent is reading the rulebook…" | `AskBox.jsx:90` |
| F7 | **Rate-limit aware** — a 429 becomes "Asking too quickly", not a raw error | `AskBox.jsx:29-35` |
| F8 | **Refocuses the input after send** | `AskBox.jsx:38` |
| F9 | **Available before any run.** An aviation-scoped box sits under the empty ADVISORIES state, so the console is not dead on arrival | `Dashboard.jsx:520-522` |
| F10 | **Refuses to invent.** Backend permits "the knowledge base does not cover that"; citations are filtered against retrieved chunks; a dead LLM degrades to a stated non-answer, never a 500 | `backend/genai/ask.py` |

## G. System health

| # | Feature | Where |
|---|---|---|
| G1 | **API status pill** from `/health/ready` | `Dashboard.jsx:488` |
| G2 | **Per-check pills** — one per dependency, green/red | `Dashboard.jsx:489-494` |
| G3 | **Degraded ≠ unreachable.** `getHealth` parses the body unconditionally, because `/health/ready` answers `503` with the *same shape* when degraded. Without this a degraded backend rendered as "unreachable" with no detail — a bug fixed during Round 2 | `api.js:31-33` |
| G4 | **Unreachable fallback** — sets an explicit `unreachable` status rather than leaving the pills blank | `Dashboard.jsx:344` |

## H. ML impact prediction

| # | Feature | Where |
|---|---|---|
| H1 | **Quantile prediction block** rendered when the result carries one | `Dashboard.jsx:538-543` |
| — | *See Gap T4-1 — this is raw JSON in a `<pre>`.* | |

## I. Site shell and supporting pages

| # | Feature | Where |
|---|---|---|
| I1 | **Dependency-free router** — pushState + popstate + anchor-scroll, ~52 lines, no routing library for a four-page site | `router.jsx` |
| I2 | **Modifier-key aware links** — Ctrl/Cmd/Shift/Alt clicks fall through to the browser for new-tab | `router.jsx:39-41` |
| I3 | **Three.js heliosphere globe** on the landing page | `helio-globe.js` (613 lines) |
| I4 | **Looping pipeline diagram** — five nodes, one rail, animated pulse with the provenance chain lighting up in step. Pure CSS keyframes, compositor-owned | `PipelineFlow.jsx`, `pages.css` |
| I5 | **Respects `prefers-reduced-motion`** — the pulse stops dead | `pages.css` |
| I6 | **Problem / Industries / About pages** with content driven from a single `data.js` | `Problem.jsx`, `Industries.jsx`, `About.jsx`, `data.js` |
| I7 | **Loading screen** | `Loader.jsx`, `loader.css` |
| I8 | **Per-page theming** — `PageShell` takes industry, G-scale and glow colour | `PageShell.jsx` |

## J. Engineering properties worth claiming

| # | Property | Evidence |
|---|---|---|
| J1 | **Three runtime dependencies.** React, ReactDOM, Three.js. No router, no state library, no component library, no test framework | `package.json` |
| J2 | **Testable without a framework.** Pure logic lives outside components and is asserted with plain node asserts | `data.test.mjs` (88 lines) |
| J3 | **Deploy-flexible.** Relative paths by default (single-origin container); `VITE_API_URL` at *build* time for split deploys, with the runtime-env pitfall documented in the source | `api.js:1-15` |
| J4 | **Responsive down to 1080px** — the two-column grid collapses to one | `dashboard.css:101-103` |
| J5 | **WebSocket origin validation** server-side | `backend/app.py:388-395` |

---

# PART 2 — WHERE WE LACK

Tiered by what would actually cost us. **Tier 1 is the section to read.**

## TIER 1 — We claim it and the console does not show it

These are not missing features so much as **claim/reality mismatches**, which is
the worst category because a judge can find them by comparing our own marketing
page to our own console.

### T1-1 · The 6-step provenance trace is never rendered. Anywhere.

The most-repeated claim in the entire project. `README.md`, `PRODUCT_BRIEF.md`
and the site's own copy all say every advisory carries a six-step provenance
trace — `raw_data → detection → impact → retrieval → verifier → output`.

- `PipelineResult` **does** carry `provenance_traces: list[dict]`
  (`backend/pipeline.py:53`).
- The backend **does** persist it to a dedicated table
  (`repository_adapter.py:131-137`).
- `Dashboard.jsx` reads `result.advisories`, `result.verified_advisories`,
  `result.errors` and `result.impact_prediction` — **and nothing else**.
  `provenance_traces` is fetched over the wire and dropped on the floor.

And `data.js:197` says, on our own site: *"All stored, all renderable."*
It is stored. It is not rendered.

> **This is the single highest-value gap in this document.** The data is already
> in the response. This is a rendering task, not an engineering task.

### T1-2 · The CV detection layer is invisible in the console

`cv_event` is a populated `StormEvent` carrying:

```
confidence: 0.96          scales: {G:5, S:3, R:5}
cme: {speed_km_s: 2200, angular_width_deg: 280, direction: "earth_directed",
      arrival_estimate: "...", confidence: 0.94,
      frame_path: "...", bbox_norm: [0.12, 0.08, 0.88, 0.86]}
flare: {class: "X5.8", r_scale: 5, onset: "..."}
l1_solar_wind: {...}      timeline: [...]      noaa_alert_raw: {...}
```

**None of it reaches the screen.** Layer 1 of a five-layer pipeline has no UI at
all. The console opens at Layer 3.

Worse for the demo: `cme.bbox_norm` is a **normalised bounding box** and
`cme.frame_path` names an **annotated coronagraph frame**. That is the single
most visually compelling asset the project has — a picture of the CME with the
detection drawn on it — and it is not on screen.

### T1-3 · Those annotated frames are not actually in the repo

Following up on T1-2, the situation is worse than "not rendered":

- `backend/data/cached/` contains only `alerts/` and `donki/`. There is **no
  `lasco/` directory**.
- `find backend/data/cached -name "*.png"` returns **0 files**.
- So `frame_path: "data/cached/lasco/2024-05/annotated/frame_008.png"` in the
  committed stub is a **dangling reference**.
- There is also **no route that serves images** — the only `FileResponse` in
  `app.py` is `/api/kb/source/{filename}` for PDFs, and there is no
  `StaticFiles` mount.
- And `.gitignore:6` states *"Annotated PNGs (~200 KB each) ARE committed"* —
  which is **not true of this tree**.

Building the CV panel therefore needs three things, not one: the frames
committed, an endpoint to serve them, and the component.

### T1-4 · Retrieval similarity is claimed as auditable and never shown

`data.js:197` promises the safety officer *"the retrieval similarity, the
confidence score, and which safety flags fired."* Two of those three are
rendered. Retrieval similarity is not surfaced anywhere in the UI.

## TIER 2 — Backend serves it, the UI throws it away

| # | Gap | Detail |
|---|---|---|
| T2-1 | **`/api/storms` returns a `completed` map that is discarded** | It carries `completed_at`, `advisory_count`, `verified_count`, `error_count` per storm (`app.py:290-306`). `Dashboard.jsx:347` reads `d.available_storms` **only**. So the selector cannot show which storms have results, when they ran, or whether they errored — despite the data arriving in the same response. |
| T2-2 | **`getAdvisory()` is dead code** | Defined at `api.js:46`, imported by nothing. `GET /api/advisory/{id}` — which returns the advisory *plus* its verified form *plus* its provenance — is never called. This is the ready-made endpoint for fixing T1-1 and it is already written. |
| T2-3 | **`/api/kb/sources` is unused** | The endpoint lists every document in the knowledge base. Nothing in the frontend calls it. There is no "browse the rulebooks" surface. |
| T2-4 | **`genai_event` unused** | Carried in `PipelineResult` (`pipeline.py:50`), never read by the UI. |
| T2-5 | **`completed_at` never displayed** | The result has a timestamp; the console never shows when a result was produced. A stale result from a previous session is indistinguishable from a fresh one. |

## TIER 3 — Interaction and workflow gaps

| # | Gap | Impact |
|---|---|---|
| T3-1 | **No cancel/stop for a running pipeline** | Once started, 65–80s is unstoppable from the UI. Ironic given the whole Round 2 feature exists because that commitment is expensive. The socket `close()` handle exists (`api.js:82`) but is only wired to unmount and re-run — not to a button. |
| T3-2 | **No run history** | Only the latest result per storm, in memory. No list of past runs, no diff between runs, no way to see that the G5 result changed after a data fix. |
| T3-3 | **No export** | Cannot download an advisory as PDF/CSV/JSON. For a product whose pitch is "regulated operators need an audit trail", there is no way to get the trail *out*. |
| T3-4 | **Health is fetched once on mount and never refreshed** | `Dashboard.jsx:344` runs in a `[]`-dep effect. A backend that degrades mid-session shows green pills indefinitely. No polling, no manual refresh. |
| T3-5 | **No retry affordance** | On error the operator must re-click Run, which re-runs pre-flight from scratch. |
| T3-6 | **Chat history is lost on collapse** | `AskBox` state is per-mount; collapsing the card or re-running clears the conversation. Deliberate ("nothing here is a system of record", `AskBox.jsx:10-11`), but it surprises users. |
| T3-7 | **No pre-flight without committing to a run** | Pre-flight only runs as a side effect of clicking Run. There is no "check this storm" button, so you cannot inspect conflicts without entering the gate flow. |
| T3-8 | **Only two storms, hardcoded** | `STORM_CONFIGS` fixes `2024-10-G4` and `2024-05-G5`. No arbitrary-date entry, no live-feed mode, no upload. |

## TIER 4 — Presentation gaps

| # | Gap | Detail |
|---|---|---|
| T4-1 | **ML impact is a raw JSON dump** | `<pre>{JSON.stringify(result.impact_prediction, null, 2)}</pre>` (`Dashboard.jsx:541`). Uncertainty quantification is one of the four pillars of the pitch — "GPS error 12.8 m, 95% CI 6.8–13.7 m" — and it renders as an unstyled blob. **A single interval bar per metric would convert the project's most defensible ML claim from invisible to obvious.** Lowest effort-to-impact ratio in this document. |
| T4-2 | **No visualisation anywhere in the console** | No timeline, no severity-over-time, no CI bars, no globe on the dashboard. The console is entirely text and pills, while the *marketing* pages carry a Three.js globe and an animated diagram. The visual budget is spent on the pages that matter least. |
| T4-3 | **No stream event timestamps** | Events show tag/step/message but no clock. You cannot tell from the log where the 80 seconds went. |
| T4-4 | **Single-slot error banner** | `error` is one string (`Dashboard.jsx:338`); a second error overwrites the first. |
| T4-5 | **No mobile layout** | The grid collapses at 1080px (`dashboard.css:101`) but the console is not designed for phones — the three-column stream rows (`84px 118px 1fr`) will crush. Acceptable for an ops console; worth stating rather than discovering on stage. |
| T4-6 | **No empty state for the ML block** | It renders only when `impact_prediction` exists, so its absence is silent — indistinguishable from "the ML layer did not run". |

## TIER 5 — Correctness and robustness risks

| # | Risk | Detail |
|---|---|---|
| T5-1 | **`verifiedById` is keyed by industry, not advisory id** | `Dashboard.jsx:439-441` builds the map from `v.industry`. The variable is *named* `verifiedById` but keyed by industry. If a run ever produces two advisories for one industry, the second silently overwrites the first and one card shows the other's verifier result. Currently safe because the pipeline emits one advisory per industry — an invariant nothing enforces. |
| T5-2 | **Array index as React key in two places** | `StreamLog` (`:106`) and `AskBox` turns (`:57`). Append-only lists, so currently harmless — fragile if either ever supports filtering or deletion. |
| T5-3 | **`getResult` failures are swallowed silently** | Three `.catch(() => {})` blocks (`:359, :380`). A 500 from the result endpoint is indistinguishable from "no result yet". |
| T5-4 | **No WebSocket reconnect** | A dropped socket mid-run ends the run from the UI's perspective. `onclose` sets `busy` false; there is no retry and no "connection lost" state distinct from "finished". |
| T5-5 | **Results are in-memory only** | `_RESULTS: dict[str, PipelineResult]` with the comment *"hackathon scope — no DB"* (`pipeline.py:58-59`), while `PRODUCT_BRIEF.md` describes "Supabase Postgres for persistence and audit". A restart loses every result. The Supabase adapter exists; whether it is the *active* repository depends on env. **Know which one is live before demoing persistence.** |

## TIER 6 — Accessibility

| # | Gap | Detail |
|---|---|---|
| T6-1 | **Advisory card header is a non-interactive element with `onClick`** | `<header className="adv-head" onClick={...}>` (`Dashboard.jsx:158`). Not keyboard-focusable, no `role="button"`, no `tabIndex`, no Enter/Space handler, no `aria-expanded`. Cards cannot be collapsed without a mouse. |
| T6-2 | **No ARIA live region on the stream** | Events append silently for screen readers during an 80-second run. |
| T6-3 | **Colour is the sole severity channel in places** | Pills carry text, which is good; the confidence bar (`:53-60`) encodes its three tones **only** in colour, with the numeric value in a separate sibling element. |
| T6-4 | **No focus management on the gate** | The pre-flight panel appears without moving focus, so keyboard users must tab to reach `Start run`. |
| T6-5 | **No skip-link or landmark structure** in the console. |

## TIER 7 — Production/scale gaps (out of hackathon scope, but ask-able)

| # | Gap |
|---|---|
| T7-1 | **No authentication or authorisation.** Anyone reaching the console can run the pipeline and spend the token budget. |
| T7-2 | **No multi-user awareness.** Two operators on the same key see neither each other's runs nor each other's quota consumption — the pre-flight quota finding says so honestly (`process-local accounting`), but the console has no concept of another user. |
| T7-3 | **No alerting or notification.** Findings and advisories are pull-only; nothing pushes. |
| T7-4 | **No role-based views.** The pitch names three audiences — operator, safety officer, engineer — and ships one screen for all three. |
| T7-5 | **No i18n.** English only, hardcoded strings. |
| T7-6 | **No telemetry on the frontend.** Prometheus covers the backend; nothing measures what operators actually click. |

---

# PART 3 — WHAT TO FIX FIRST

Ranked by **judge-visible impact ÷ effort**. The top three are all rendering
work against data that already arrives in the response.

| # | Fix | Effort | Why it ranks here |
|---|---|---|---|
| 1 | **Render the ML impact block properly** (T4-1) | ~1h | Converts the most defensible ML claim in the project from a JSON blob into a visible interval. Pure frontend, data already present. |
| 2 | **Render the provenance trace** (T1-1) | ~2h | Closes the loudest claim/reality gap. `provenance_traces` already arrives; `getAdvisory()` is already written and unused. A `<details>` chain per advisory would do it. |
| 3 | **Add a detection/StormEvent panel** (T1-2) | ~2h | Makes Layer 1 exist in the UI. G/S/R scales, CME kinematics, flare class — all already in `cv_event`. |
| 4 | **Use the `completed` map in the storm selector** (T2-1) | ~30m | Shows which storms have results and when. Data already in the same response the selector already parses. |
| 5 | **Refresh health on an interval** (T3-4) | ~15m | One `setInterval`. Removes a stale-state trap during a long demo. |
| 6 | **Fix the card-header accessibility** (T6-1) | ~15m | `role="button"`, `tabIndex={0}`, key handler, `aria-expanded`. Four attributes. |
| 7 | **Add a cancel button** (T3-1) | ~30m | The `close()` handle already exists; wire it to a button. Thematically strong — the whole Round 2 feature is about respecting an expensive commitment. |
| 8 | **Rename or re-key `verifiedById`** (T5-1) | ~10m | Either key it by `advisory_id` or rename it `verifiedByIndustry`. A latent bug with a misleading name. |
| 9 | **Commit the annotated frames + add an image route** (T1-3) | ~3h | Highest *visual* payoff of anything here, but the only item needing backend work and new binary assets. |
| 10 | **Stream event timestamps** (T4-3) | ~20m | Makes the 80 seconds legible. |

---

# APPENDIX — Claim vs. reality

For pre-demo honesty. Every row is something our own documentation or site copy
asserts; the right column is what the console actually does today.

| We say | Console reality | Verdict |
|---|---|---|
| "6-step provenance per advisory" (`data.js:189`) | Fetched, never rendered | **Gap** |
| "All stored, all renderable" (`data.js:197`) | Stored ✓, rendered ✗ | **Gap** |
| "The retrieval similarity … all of it renderable" (`data.js:197`) | Not surfaced | **Gap** |
| "Annotated PNGs ARE committed" (`.gitignore:6`) | 0 PNGs on disk, no `lasco/` dir | **False for this tree** |
| "GPS error 12.8 m, 95% CI 6.8–13.7 m" (`PRODUCT_BRIEF`) | Raw JSON dump | **Present but unpresented** |
| "Supabase Postgres for persistence and audit" (`PRODUCT_BRIEF`) | `_RESULTS` in-memory dict, "hackathon scope — no DB" | **Depends on env — verify before claiming** |
| "Pre-flight warns and offers Run anyway" (`PRODUCT_BRIEF`) | Correct behaviour, but the label is now **`Start run`** — "Run anyway" was deliberately removed | **Doc is stale** |
| Pre-flight never hard-blocks | ✓ Verified `Dashboard.jsx:301` | **True** |
| Citations open the source at the cited page | ✓ Verified `citation.js` + `#page=N` | **True** |
| Verifier shows proposed vs. corrected | ✓ Verified `Dashboard.jsx:207-218` | **True** |
| Chat cannot starve a pipeline run | ✓ Separate model → separate TPM bucket | **True** |
| Three runtime dependencies | ✓ React, ReactDOM, Three.js | **True** |

---

*Generated from a full read of `frontend/src/` and the backend route contract.
Nothing in the gap section is hidden elsewhere in the docs — this is intended to
be the document a hostile reviewer would otherwise write for us.*
