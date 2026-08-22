/* All copy from the Claude Design artboards, verbatim. */

export const INDUSTRIES = [
  {
    key: 'aviation', name: 'AVIATION', source: 'ICAO NAT DOC 007',
    status: 'critical at G4', tagline: 'HF radio over polar routes, GPS accuracy, crew radiation dose',
    chips: ['GPS ERROR 12.8 M', 'HF BLACKOUT 85%'],
    lede: 'Routed CRITICAL by a hard-coded matrix, never by a model.',
    rest: 'The verifier holds reroutes at 70°N for G4 and rewrites any HF fallback outside the ICAO NAT set {3, 5, 8, 11, 17} MHz before an operator sees it.'
  },
  {
    key: 'grid', name: 'POWER GRID', source: 'NERC TPL-007-4',
    status: 'critical at G4', tagline: 'Geomagnetically induced currents in transformers',
    chips: ['GIC STEPS VERIFIED', 'KP 8.3 · CME 1480 KM/S'],
    lede: 'Transformer heating, voltage instability, blackout risk.',
    rest: 'Operating steps are checked against NERC TPL-007-4 Appendix B keywords by a zero-LLM rule engine. A step that does not match is blocked, not softened.'
  },
  {
    key: 'maritime', name: 'MARITIME', source: 'IMO GMDSS 2019',
    status: 'high at G4', tagline: 'GMDSS distress comms, GNSS positioning',
    chips: ['GMDSS CHANNELS CHECKED', 'GNSS DEGRADED'],
    lede: 'Degraded safety-of-life comms in remote waters.',
    rest: 'Distress and working channels are validated against the GMDSS set. An invalid channel blocks the advisory rather than shipping a plausible-sounding frequency.'
  },
  {
    key: 'telecom', name: 'TELECOM', source: 'NO KB · BY DESIGN',
    status: 'high at G4', tagline: 'HF and satellite links, timing signals',
    chips: ['LOW_COVERAGE FLAGGED', 'TELECOM_KB 0 CHUNKS'],
    lede: 'The telecom knowledge base is intentionally empty.',
    rest: 'So every telecom advisory carries LOW_COVERAGE. It is a deliberate demonstration that the system reports thin evidence instead of inventing it.'
  }
]

export const KP = { 1: '5.0', 2: '6.0', 3: '7.0', 4: '8.3', 5: '9.0' }

/** Step the carousel index by `d`, wrapping in both directions. */
export const wrap = (i, d, n = INDUSTRIES.length) => (i + d + n) % n

export const GLYPHS = [
  { l: '20%', t: '8%', c: '+' },
  { l: '32%', t: '62%', c: '+' },
  { l: '69%', t: '22%', c: '+' },
  { l: '78%', t: '70%', c: '+' },
  { l: '26%', t: '34%', c: '△', size: 8 },
  { l: '73%', t: '47%', c: '△', size: 8 },
  { l: '57%', t: '9%', c: '◇', size: 8 },
  { l: '44%', t: '78%', c: '◇', size: 8 }
]

/* `path` is what decides the active underline; the dashboard link lands on
   /about but never claims the ABOUT tab. */
export const NAV = [
  { label: 'MAIN', to: '/', path: '/' },
  { label: 'ABOUT', to: '/about', path: '/about' },
  { label: 'PROBLEM', to: '/problem', path: '/problem' },
  { label: 'INDUSTRIES', to: '/industries', path: '/industries' },
  { label: 'CONSOLE', to: '/dashboard', path: '/dashboard' }
]

export const DASHBOARD_LINK = '/dashboard'

/* ---------- Boot sequence ----------
   The problem statement in four beats, timed against the globe's rise. Beat 03
   is GAPS[01] compressed — keep them saying the same thing. */

export const BOOT_BEATS = [
  { line: 'A CME LEAVES THE SUN', sub: '93 MILLION MILES · 18 HOURS OF WARNING' },
  { line: 'THE ALERT DESCRIBES THE SKY', sub: 'G4 WATCH · Kp 8.3 · S2 · R3' },
  { line: 'THE OPERATOR HAS TO ACT ON AN AIRCRAFT', sub: 'AVIATION · POWER GRID · MARITIME · TELECOM' },
  { line: 'HELIOOPS', sub: 'LAYER 3 ADVISORY SURFACE' }
]

/* ---------- About ---------- */

export const ABOUT_STATS = [
  '4 INDUSTRIES', '5 PIPELINE STAGES', '6-STEP PROVENANCE',
  '10 GUARDRAIL LAYERS', '0 RNG IN DETECTION'
]

export const STAGES = [
  { n: '01', title: 'CV DETECTION', body: 'A deterministic CME detector on running-difference coronagraph frames, fused with NASA DONKI physics, GOES XRS flare class and DSCOVR solar wind. A threshold algorithm with no RNG: the same frame gives byte-identical output every run.', out: '→ StormEvent · G/S/R scales' },
  { n: '02', title: 'ML IMPACT', body: 'Six LightGBM quantile models, not point estimators. Every prediction ships as a median with a 2.5th and 97.5th percentile, so an operator is told the interval instead of a bare number with invisible error bars.', out: '→ GPS error ±95% CI · HF blackout ±95% CI' },
  { n: '03', title: 'AGENTIC ADVISORY', body: 'Deterministic G-scale routing fans out to four industry agents in parallel, each grounded by RAG on the real rulebooks, behind ten layers of anti-hallucination control.', out: '→ 4 advisories · sources cited' },
  { n: '04', title: 'DETERMINISTIC VERIFIER', body: 'A zero-LLM rule engine re-checks every advisory against authoritative constants: ICAO HF bands, reroute latitudes, NERC GIC steps, GMDSS channels. It corrects and records; it does not just flag.', out: '→ passed · corrected · blocked' },
  { n: '05', title: 'DELIVERY', body: 'FastAPI REST and WebSocket streaming into an operations dashboard, persisted to Postgres for audit. Detection, prediction, agent reasoning and verifier checks land on screen as they happen.', out: '→ live stream · stored trace' }
]

export const BETS = [
  { tag: 'DESIGN BET 01', title: 'Deterministic where safety demands it', body: 'The G-scale to industry-severity matrix is a hard-coded lookup table, not a model output. A G4 storm always produces CRITICAL aviation status — never HIGH because a sampler rolled differently. The LLM only does the part LLMs are good at: turning a severity tier plus retrieved regulatory text into readable, numbered steps.' },
  { tag: 'DESIGN BET 02', title: 'The LLM is never the last word', body: 'An agent writes "switch to 21 MHz". The verifier catches the number, tests it against the ICAO NAT set {3, 5, 8, 11, 17}, rejects it, rewrites the action to 5 MHz, records the correction and streams it to the dashboard as a visible block event. The operator sees both what the model proposed and what the rules enforced.' },
  { tag: 'DESIGN BET 03', title: 'Physics from authoritative sources', body: 'CME speed, angular width and direction come from NASA DONKI, a human-reviewed database. Flare class comes from GOES XRS. Solar wind Bz and speed come from DSCOVR at L1. We did not train a regressor to guess numbers a NASA API already publishes and a regulator would accept.' },
  { tag: 'DESIGN BET 04', title: 'Failure is designed in, not discovered', body: 'No cached imagery falls back to stub storm events. DONKI unreachable falls back to cached physics. Missing ML checkpoints fall back to conservative defaults. Three exhausted LLM retries produce an advisory that says ESCALATE TO SPECIALIST instead of a guess.' }
]

export const REAL = [
  'The detection algorithm and the DONKI / GOES / DSCOVR integrations',
  'The trained impact models and their measured interval coverage',
  'The four-agent pipeline and the deterministic verifier',
  'The API, the dashboard and the database schema',
  'Docker → CI → Kubernetes → Terraform → ArgoCD → chaos → runbooks',
  '~137 Python tests and ~255 frontend tests'
]

export const CAVEATS = [
  'Impact models are trained on synthetic storm data. R² of 0.986 measures how well the model learned the physical proxy rules it was generated from, not real-world accuracy. NASA OMNIWeb historical data is the known next step.',
  'Two demo storms are wired for replay: 2024-10-G4 and 2024-05-G5. Live mode exists; the cached path is what the demo runs.',
  'telecom_kb is intentionally empty, so the telecom agent honestly emits LOW_COVERAGE.',
  'CI gates are advisory, not blocking. Full CD is scaffolded, not switched on.',
  'Rate limiting and metrics are per-process — correct on a single replica, needing a shared store before horizontal scaling means anything.'
]

export const TEAM = [
  { name: 'Neal', layer: 'LAYER 1', role: 'CV detection, ML integration, dashboard, backend security' },
  { name: 'Parshva', layer: 'LAYER 2', role: 'ML impact models, synthetic data, data engineering' },
  { name: 'Priyanshu', layer: 'LAYER 3', role: 'GenAI advisory, verifier, backend pipeline, database' },
  { name: 'Tirth', layer: 'LAYER 4', role: 'Frontend dashboard, DevOps, deployment' }
]

/* ---------- Problem ---------- */

export const GAPS = [
  { n: '01', title: 'Raw alerts are not decisions', body: '"G4 Watch, Kp 8.3" tells a dispatcher nothing about which of their 40 polar flights to move, or which frequency to fall back to. The alert describes the sky; the operator has to act on an aircraft.' },
  { n: '02', title: 'The rulebooks are PDFs', body: 'The actual procedures live in ICAO NAT Doc 007, NERC TPL-007-4 and IMO GMDSS 2019 — hundreds of pages, per industry, that nobody reads at 3am during an event.' },
  { n: '03', title: 'Generic LLMs are unsafe here', body: 'Ask a chatbot for an HF fallback frequency and it will confidently invent one. There is no mechanism in a chat interface that stops a plausible number from reaching a cockpit.' },
  { n: '04', title: 'Nothing is auditable', body: 'Regulated operators cannot act on an output they cannot trace back to a cited procedure and a measured input. Without provenance, a correct answer is still unusable.' }
]

export const IMPACT_ROWS = [
  { name: 'AVIATION', breaks: 'HF radio over polar routes, GPS accuracy, crew radiation dose', consequence: 'Polar tracks close; flights reroute or cancel', sev: 'CRITICAL', color: '#ff8a6a' },
  { name: 'POWER GRID', breaks: 'Geomagnetically induced currents in transformers', consequence: 'Transformer heating, voltage instability, blackout risk', sev: 'CRITICAL', color: '#ff8a6a' },
  { name: 'MARITIME', breaks: 'GMDSS distress comms, GNSS positioning', consequence: 'Degraded safety-of-life comms in remote waters', sev: 'HIGH', color: '#f3ab5c' },
  { name: 'TELECOM', breaks: 'HF and satellite links, timing signals', consequence: 'Link outages, timing drift', sev: 'HIGH', color: '#f3ab5c' }
]

export const SIGNALS = [
  { src: 'NOAA / SWPC', gives: 'Storm alerts and watches', note: 'Public text alerts. Accurate about the sky, silent about your fleet.' },
  { src: 'NASA DONKI', gives: 'CME kinematics', note: 'Human-reviewed speed, angular width and direction. A regulator would accept it.' },
  { src: 'GOES XRS', gives: 'Flare class', note: 'X-ray flux mapped to the R-scale. X1.8 in October 2024; X5.8 in May 2024.' },
  { src: 'DSCOVR AT L1', gives: 'Solar wind Bz and speed', note: 'Measured upstream, roughly an hour before arrival at Earth.' }
]

/* ---------- Industries ---------- */

export const IND_DETAIL = [
  {
    key: 'aviation', name: 'AVIATION', sev: 'CRITICAL', sevColor: '#ff8a6a', source: 'ICAO NAT DOC 007 · 242 CHUNKS',
    body: 'HF radio over polar routes degrades, GPS accuracy drops and crew radiation dose climbs. The advisory names the reroute latitude and the fallback frequency instead of telling a dispatcher that a storm is coming.',
    saves: 'Which polar flights to move, and to which latitude — rather than a blanket closure.',
    rule: 'Reroute latitude held at 78°N for G3, 70°N for G4, 60°N for G5.'
  },
  {
    key: 'grid', name: 'POWER GRID', sev: 'CRITICAL', sevColor: '#ff8a6a', source: 'NERC TPL-007-4 · 101 CHUNKS',
    body: 'Geomagnetically induced currents heat transformers and destabilise voltage. Operating steps are drawn from the standard itself, so an operator is reading their own compliance language back.',
    saves: 'A named operating step instead of a judgement call under load.',
    rule: 'GIC steps matched against TPL-007-4 Appendix B keywords, or blocked.'
  },
  {
    key: 'maritime', name: 'MARITIME', sev: 'HIGH', sevColor: '#f3ab5c', source: 'IMO GMDSS 2019 · 2 CHUNKS',
    body: 'GMDSS distress comms and GNSS positioning degrade in exactly the remote waters where there is no alternative. Thin evidence is reported as thin, not padded out.',
    saves: 'A validated distress channel rather than a plausible-sounding frequency.',
    rule: 'Channel checked against the valid distress and working set, or blocked.'
  },
  {
    key: 'telecom', name: 'TELECOM', sev: 'HIGH', sevColor: '#f3ab5c', source: 'NO KNOWLEDGE BASE · BY DESIGN',
    body: 'HF and satellite links drop and timing drifts. The telecom knowledge base is intentionally empty, so every telecom advisory carries LOW_COVERAGE — a deliberate demonstration that the system reports thin evidence instead of inventing it.',
    saves: 'An honest signal that the system does not have the rulebook for this one.',
    rule: 'LOW_COVERAGE flag raised on every advisory, by design.'
  }
]

export const COSTS = [
  { figure: 'CPU', label: 'NO GPU ANYWHERE', note: 'Threshold detection, LightGBM impact, BGE-small embeddings — all CPU-only.' },
  { figure: '< 500 KB', label: 'MODEL CHECKPOINTS', note: 'Six quantile models. The whole impact layer fits in a Git LFS afterthought.' },
  { figure: '384-d', label: 'EMBEDDING WIDTH', note: 'BGE-small-en-v1.5 over four rulebook collections, built once and reused.' },
  { figure: 'FREE', label: 'DATA INPUTS', note: 'NOAA, DONKI, GOES and DSCOVR are public. The paid dependency is the LLM alone.' }
]

export const COMPARE_HEAD = ['RAW NOAA', 'GENERIC LLM', 'MANUAL DESK', 'HELIOOPS']

export const COMPARE = [
  { row: 'Per-industry actions', a: '✗', b: '~', c: '✓', d: '✓' },
  { row: 'Grounded in real rulebooks', a: '✗', b: '✗', c: '✓', d: 'ICAO / NERC / IMO / NOAA' },
  { row: 'Safety-critical values verified', a: 'n/a', b: '✗', c: '~', d: 'deterministic rule engine' },
  { row: 'Quantified uncertainty', a: '✗', b: '✗', c: '~', d: '95% CIs, measured coverage' },
  { row: 'Full audit trail', a: '✗', b: '✗', c: '~', d: '6-step provenance per advisory' },
  { row: 'Reproducible', a: '✓', b: '✗', c: '✗', d: 'no RNG in detection or routing' },
  { row: 'Real time', a: '✓', b: 'n/a', c: '✗', d: 'WebSocket streaming' },
  { row: 'Cost to run', a: 'free', b: 'low', c: 'very high', d: 'low · CPU-only' }
]

export const AUDIENCES = [
  { who: 'FOR THE OPERATOR', title: 'One screen, four industries, live', body: 'Trigger a storm and watch detection, prediction, four agents reasoning in parallel and verifier checks land in real time. Each advisory is a numbered action list with a time window and a cited source.' },
  { who: 'FOR THE SAFETY OFFICER', title: 'Traceable end to end', body: 'Which chunk of which PDF grounded step 3. What the model originally proposed before correction. The retrieval similarity, the confidence score, and which safety flags fired. All stored, all renderable.' },
  { who: 'FOR THE ENGINEERING TEAM', title: 'Built to be operated', body: 'Structured JSON logs, Prometheus metrics, three-tier health checks, Kubernetes manifests with real probes, Terraform for the cluster, GitOps for deploys, chaos experiments in staging and four incident runbooks.' }
]

/* ---------- footer ---------- */

export const FOOTER_SOURCES = ['NOAA / SWPC alerts', 'NASA DONKI', 'GOES XRS', 'DSCOVR at L1']

export const FOOTER_RULEBOOKS = [
  'ICAO NAT Doc 007 · 242 chunks',
  'NERC TPL-007-4 · 101 chunks',
  'NOAA scales · 166 chunks',
  'IMO GMDSS 2019 · 2 chunks'
]
