import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import AskBox from './AskBox.jsx'
import {
  citationUrl,
  getHealth,
  getPreflight,
  getResult,
  getStorms,
  runPipeline,
  streamPipeline,
} from './api.js'
import { elapsed } from './console.js'
import {
  DetectionPanel,
  Empty,
  ImpactPanel,
  Pill,
  ProvenancePanel,
  SourcesPanel,
  VerifierPanel,
} from './panels.jsx'
// toneOf is already taken below by the stream-event colouring.
import { SEVERITIES, gateDecision, toneOf as severityTone } from './preflight.js'
import { Link } from './router.jsx'
import './dashboard.css'

/* The operator-facing surface for the whole pipeline.

   One panel per layer, selected from the rail on the left, because the pipeline
   has five stages and a single scrolling page made three of them invisible.
   Every panel renders fields the backend already returns; the data contract is
   the part worth keeping. */

const SEVERITY_ORDER = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1, NONE: 0 }

// Flags are informational, never blocking — but they are not equally serious.
const FLAG_TONE = {
  GENERATION_FAILED: 'bad',
  HALLUCINATION_DETECTED: 'warn',
  CITATION_GAP: 'warn',
  SEVERITY_MISMATCH: 'warn',
  LOW_CONFIDENCE: 'warn',
  LOW_COVERAGE: 'info'
}

const VERIFIER_TONE = {
  passed: 'ok',
  passed_with_corrections: 'warn',
  blocked: 'bad',
  not_applicable: 'info'
}

const INDUSTRIES = ['aviation', 'grid', 'maritime', 'telecom']

const pct = n => `${Math.round((n ?? 0) * 100)}%`

function ConfidenceBar({ value }) {
  const tone = value >= 0.75 ? 'ok' : value >= 0.5 ? 'warn' : 'bad'
  return (
    <div className="confbar" title={`confidence ${pct(value)}`}>
      <div className={`confbar-fill is-${tone}`} style={{ width: `${(value ?? 0) * 100}%` }} />
    </div>
  )
}

/* ---------- Stream log ---------- */

/* Not every event carries `message`. verifier.check and advisory.verified are
   structured rather than prose, and they are the two most interesting lines in
   a run — a blocked check is the deterministic layer overruling the model — so
   they get rendered rather than shown as a blank row. */
function describe(e) {
  switch (e.event) {
    case 'verifier.check':
      return e.status === 'blocked'
        ? `${e.field}: ${e.proposed} REJECTED → corrected to ${e.corrected_to}`
        : `${e.field}: ${e.proposed} ok`
    case 'advisory.verified':
      return `verifier ${e.verifier_status}${e.requires_human ? ' · requires human review' : ''}`
    case 'advisory.generated':
      return `severity ${e.severity} · confidence ${pct(e.confidence)}`
    case 'pipeline.complete':
      return `${e.total_advisories} advisories: ${(e.industries ?? []).join(', ')}`
    default:
      return e.message ?? ''
  }
}

function toneOf(e) {
  if (e.event === 'error' || e.event === 'agent.error' || e.event === 'pipeline.error') return 'bad'
  if (e.event === 'verifier.check') return e.status === 'blocked' ? 'bad' : 'ok'
  if (e.event === 'advisory.verified') return e.verifier_status === 'passed' ? 'ok' : 'warn'
  if (e.event === 'advisory.generated' || e.event === 'pipeline.complete') return 'ok'
  return 'plain'
}

function StreamLog({ events, startedAt }) {
  const endRef = useRef(null)
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'nearest' })
  }, [events.length])

  if (!events.length) {
    return (
      <Empty>
        No run yet. Start one from RUN CONTROL and every stage reports here as it
        happens — retrieval, generation, and each deterministic check the verifier
        makes, in the order they occur.
      </Empty>
    )
  }

  return (
    /* Screen readers get the run narrated rather than 80 seconds of silence. */
    <div className="streamlog" role="log" aria-live="polite" aria-label="pipeline events">
      {events.map((e, i) => {
        const tag = e.industry ?? e.stage ?? e.event.split('.')[0]
        return (
        <div key={i} className={`streamline tone-${toneOf(e)}`}>
          <span className="streamline-clock">{elapsed(startedAt, e._at)}</span>
          <span className="streamline-tag" title={tag}>{tag}</span>
          <span className="streamline-step">{e.step ?? e.event}</span>
          <span className="streamline-msg">{describe(e)}</span>
        </div>
        )
      })}
      <div ref={endRef} />
    </div>
  )
}

/* ---------- Advisory ---------- */

/* A citation the operator can actually follow.

   source_ref carries a page now ("nat_doc_007_2025.pdf p.42"), so this opens
   the source document at that page in a new tab using the browser's own PDF
   viewer. A ref that names no file (a bare regulation code) stays plain text
   rather than becoming a dead link. */
function Citation({ refText }) {
  if (!refText) return null
  const href = citationUrl(refText)
  if (!href) {
    return (
      <span className="act-cite" title="source_ref - must resolve to a retrieved chunk">
        {refText}
      </span>
    )
  }
  return (
    <a
      className="act-cite act-cite-link"
      href={href}
      target="_blank"
      rel="noreferrer"
      title={`open ${refText}`}
    >
      {refText}
    </a>
  )
}


function AdvisoryCard({ advisory, verified }) {
  const [open, setOpen] = useState(true)
  const flags = advisory.safety_flags ?? []
  const vstatus = verified?.verifier?.status
  const checks = verified?.verifier?.checks ?? []
  const corrections = checks.filter(c => c.status === 'blocked')

  return (
    <section className="adv">
      {/* A collapse the keyboard can reach. It was a bare <header onClick>, so
          the cards could only be folded with a mouse. */}
      <header
        className="adv-head"
        role="button"
        tabIndex={0}
        aria-expanded={open}
        onClick={() => setOpen(o => !o)}
        onKeyDown={e => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            setOpen(o => !o)
          }
        }}
      >
        <div className="adv-title">
          <span className="adv-industry">{advisory.industry}</span>
          <Pill tone={SEVERITY_ORDER[advisory.severity] >= 4 ? 'bad' : 'warn'}>
            {advisory.severity}
          </Pill>
        </div>
        <div className="adv-meta">
          <ConfidenceBar value={advisory.confidence_score} />
          <span className="small muted">{pct(advisory.confidence_score)}</span>
          <span className="chev">{open ? '−' : '+'}</span>
        </div>
      </header>

      {open && (
        <div className="adv-body">
          <p className="adv-summary">{advisory.summary}</p>

          <div className="adv-flags">
            {flags.length === 0 ? (
              <Pill tone="ok">no guardrail flags</Pill>
            ) : (
              flags.map(f => (
                <Pill key={f} tone={FLAG_TONE[f] ?? 'warn'} title="Guardrail flag — advisory still delivered for review">
                  {f}
                </Pill>
              ))
            )}
            {vstatus && (
              <Pill tone={VERIFIER_TONE[vstatus] ?? 'info'} title="Deterministic verifier result">
                verifier: {vstatus}
              </Pill>
            )}
            {verified?.requires_human && <Pill tone="bad">requires human review</Pill>}
          </div>

          <ol className="adv-actions">
            {advisory.action_items.map(a => (
              <li key={a.step}>
                <div className="act-text">{a.action}</div>
                <div className="act-meta">
                  <span className="act-when">{a.time_window}</span>
                  <Citation refText={a.source_ref} />
                </div>
                <div className="act-why muted small">{a.rationale}</div>
              </li>
            ))}
          </ol>

          {corrections.length > 0 && (
            <div className="verifier-box">
              <div className="col-head">VERIFIER CORRECTIONS</div>
              {corrections.map((c, i) => (
                <div key={i} className="vcheck">
                  <code>{c.field}</code> proposed <b>{String(c.proposed)}</b> → corrected to{' '}
                  <b>{String(c.corrected_to)}</b>
                  <div className="muted small">{c.reason}</div>
                </div>
              ))}
            </div>
          )}

          {checks.length > 0 && corrections.length === 0 && (
            <div className="muted small">
              {checks.length} deterministic check{checks.length === 1 ? '' : 's'} passed:{' '}
              {checks.map(c => c.field).join(', ')}
            </div>
          )}

          {advisory.generation_errors?.length > 0 && (
            <details className="gen-errors">
              <summary className="small muted">
                {advisory.generation_errors.length} generation note(s)
              </summary>
              <ul>
                {advisory.generation_errors.map((e, i) => (
                  <li key={i} className="small muted">
                    {e}
                  </li>
                ))}
              </ul>
            </details>
          )}

          <div className="adv-sources small muted">
            sources cited: {(advisory.sources_cited ?? []).join(' · ') || '—'}
          </div>

          {/* Scoped chat: the card already knows the industry and the advisory,
              so the agent never has to ask which one. */}
          <AskBox
            industry={advisory.industry}
            advisoryId={advisory.advisory_id}
            Citation={Citation}
          />
        </div>
      )}
    </section>
  )
}

/* ---------- Pre-flight ---------- */

/* Progressive disclosure before the 65-80s commit.

   Layer 1 states the single most important consequence as one plain sentence
   (a count of warnings is a tally, not information — the sentence is what
   decides the click). Layer 2, behind <details>, carries the evidence.

   Never hard-blocks: even a `block` finding leaves the run available, and its
   detail explains the 429 that will follow. One button label, always the same
   word — "Run" vs "Run anyway" both ran, which only read as ambiguity. */
function PreflightPanel({ gate, onConfirm, onCancel }) {
  if (gate.phase === 'loading') {
    return (
      <div className="preflight">
        <span className="col-head">PRE-FLIGHT</span>
        <span className="muted small">checking cached inputs, conflicts and quota…</span>
      </div>
    )
  }

  const { findings, counts, estimate, headline, tone } = gate.decision

  return (
    <div className="preflight">
      <div className="preflight-head">
        <span className="col-head">PRE-FLIGHT</span>
        {SEVERITIES.map(
          sev =>
            counts[sev] > 0 && (
              <Pill key={sev} tone={severityTone(sev)}>
                {counts[sev]} {sev}
              </Pill>
            )
        )}
        {findings.length === 0 && <Pill tone="ok">clear</Pill>}
        {estimate != null && <span className="muted small">est ~{estimate}s</span>}
      </div>

      <p className={`preflight-headline tone-${tone}`}>{headline}</p>

      <div className="preflight-actions">
        <button className="btn btn-primary" onClick={onConfirm}>
          Start run
        </button>
        <button className="btn" onClick={onCancel}>
          Cancel
        </button>
      </div>

      {findings.length > 0 && (
        <details className="preflight-findings">
          <summary className="small muted">
            show all {findings.length} finding{findings.length === 1 ? '' : 's'}
          </summary>
          <ul>
            {findings.map(f => (
              <li key={f.id}>
                <Pill tone={severityTone(f.severity)}>{f.severity}</Pill>{' '}
                <span className="preflight-title">{f.title}</span>
                <div className="muted small">{f.detail}</div>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}

/* ---------- Run control ---------- */

/* The `completed` map arrives in the same /api/storms response the selector
   already parses, and used to be thrown away — so a storm with results looked
   identical to one that had never run. */
function StormRow({ id, meta, selected, disabled, onSelect }) {
  return (
    <button
      className={`storm-row${selected ? ' is-selected' : ''}`}
      onClick={() => onSelect(id)}
      disabled={disabled}
      aria-pressed={selected}
    >
      <span className="storm-id">{id}</span>
      {meta ? (
        <span className="storm-meta small muted">
          {meta.advisory_count} advisories · {meta.verified_count} verified
          {meta.error_count > 0 && <span className="storm-err"> · {meta.error_count} errors</span>}
          <br />
          {String(meta.completed_at).replace('T', ' ').slice(0, 19)} UTC
        </span>
      ) : (
        <span className="storm-meta small muted">no run this session</span>
      )}
    </button>
  )
}

function RunPanel({
  storms, completed, stormId, setStormId, busy, gate,
  onRun, onCancelRun, onConfirmGate, onCancelGate, result,
}) {
  return (
    <>
      <div className="panel-lede">
        Two anchor storms replay deterministically. A run is a 65–80&nbsp;s
        commitment — the reasoning pass dominates — so every run passes a
        pre-flight check first, and the check never blocks the run.
      </div>

      <div className="col-head">STORM</div>
      <div className="storm-list">
        {storms.length === 0 && <Empty>Backend unreachable — no storms available.</Empty>}
        {storms.map(s => (
          <StormRow
            key={s}
            id={s}
            meta={completed?.[s]}
            selected={s === stormId}
            disabled={busy || gate != null}
            onSelect={setStormId}
          />
        ))}
      </div>

      <div className="run-actions">
        <button className="btn btn-primary" onClick={() => onRun('live')} disabled={busy || !stormId || gate != null}>
          {busy ? 'Running…' : 'Run live (WebSocket)'}
        </button>
        <button className="btn" onClick={() => onRun('batch')} disabled={busy || !stormId || gate != null}>
          Run batch (REST)
        </button>
        {/* The whole pre-flight feature exists because 80s is expensive to
            commit to. Not being able to stop it once started was the same
            problem one step later. */}
        {busy && (
          <button className="btn btn-stop" onClick={onCancelRun}>
            Stop run
          </button>
        )}
      </div>

      {gate && (
        <PreflightPanel gate={gate} onConfirm={onConfirmGate} onCancel={onCancelGate} />
      )}

      {result?.completed_at && (
        <div className="small muted run-stamp">
          Showing the result produced {String(result.completed_at).replace('T', ' ').slice(0, 19)} UTC.
        </div>
      )}
    </>
  )
}

/* ---------- Page ---------- */

export default function Dashboard() {
  const [storms, setStorms] = useState([])
  const [completed, setCompleted] = useState({})
  const [stormId, setStormId] = useState('')
  const [health, setHealth] = useState(null)
  const [events, setEvents] = useState([])
  const [startedAt, setStartedAt] = useState(null)
  const [result, setResult] = useState(null)
  // Partial layer output hydrated from the stream while a run is still going.
  const [live, setLive] = useState({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [panel, setPanel] = useState('run')
  const [askIndustry, setAskIndustry] = useState('aviation')
  // Pre-flight gate: null | {phase:'loading'|'confirm', runner:'live'|'batch', data?}
  const [gate, setGate] = useState(null)
  const closeRef = useRef(null)

  const loadStorms = useCallback(
    () =>
      getStorms()
        .then(d => {
          setStorms(d.available_storms ?? [])
          setCompleted(d.completed ?? {})
          setStormId(prev => prev || d.available_storms?.[0] || '')
        })
        .catch(e => setError(String(e.message ?? e))),
    []
  )

  // Health once on mount, then on a timer: a backend that degrades mid-demo
  // used to keep showing green pills for the rest of the session.
  useEffect(() => {
    const poll = () => getHealth().then(setHealth).catch(() => setHealth({ status: 'unreachable' }))
    poll()
    const t = setInterval(poll, 15_000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    loadStorms()
  }, [loadStorms])

  // Whenever the selected storm changes, show any result already on the server.
  useEffect(() => {
    if (!stormId) return
    setResult(null)
    getResult(stormId)
      .then(setResult)
      .catch(() => {})
  }, [stormId])

  useEffect(() => () => closeRef.current?.(), [])

  const startLive = useCallback(() => {
    if (!stormId || busy) return
    setBusy(true)
    setError(null)
    setEvents([])
    setResult(null)
    setLive({})
    setStartedAt(Date.now())
    setPanel('stream')
    closeRef.current?.()
    closeRef.current = streamPipeline(stormId, {
      // Stamped on arrival: the backend does not clock its own events, and when
      // the UI saw them is the honest answer to "where did the 80 seconds go".
      onEvent: e => {
        setEvents(prev => [...prev, { ...e, _at: Date.now() }])
        if (e.event === 'error') setError(e.message)
        // Layers 1 and 2 finish in the first couple of seconds; without this
        // their panels sit empty for the remaining ~70s of a run that has
        // already computed them. The detection event carries scales and
        // confidence only — the full StormEvent arrives with the result.
        if (e.event === 'pipeline.stage' && e.status === 'completed' && e.data) {
          if (e.stage === 'detection') setLive(l => ({ ...l, cv_event: e.data }))
          if (e.stage === 'impact_prediction') setLive(l => ({ ...l, impact_prediction: e.data }))
        }
      },
      onClose: () => {
        setBusy(false)
        // The stream carries advisories, but the persisted result also has the
        // verifier output and provenance, which only exist after the run.
        getResult(stormId).then(setResult).catch(() => {})
        loadStorms()
      },
      onError: e => {
        setError(String(e.message ?? e))
        setBusy(false)
      }
    })
  }, [stormId, busy, loadStorms])

  const startBatch = useCallback(async () => {
    if (!stormId || busy) return
    setBusy(true)
    setError(null)
    setEvents([])
    try {
      setResult(await runPipeline(stormId))
      setPanel('advisories')
      loadStorms()
    } catch (e) {
      setError(String(e.message ?? e))
    } finally {
      setBusy(false)
    }
  }, [stormId, busy, loadStorms])

  const startRunner = useCallback(
    runner => (runner === 'live' ? startLive() : startBatch()),
    [startLive, startBatch]
  )

  // Closing the socket ends the run from the UI's side. The backend finishes
  // its own work; this stops us waiting on it.
  const cancelRun = useCallback(() => {
    closeRef.current?.()
    setBusy(false)
  }, [])

  // Every run goes through the gate: preflight first, confirm, then start.
  // If preflight itself fails, start directly — the gate never breaks the demo.
  const requestRun = useCallback(
    runner => {
      if (!stormId || busy || gate) return
      setGate({ phase: 'loading', runner })
      getPreflight(stormId)
        .then(data => {
          const decision = gateDecision(data)
          if (decision.action === 'run') {
            setGate(null)
            startRunner(runner)
          } else {
            setGate({ phase: 'confirm', runner, decision })
          }
        })
        .catch(() => {
          setGate(null)
          startRunner(runner)
        })
    },
    [stormId, busy, gate, startRunner]
  )

  const confirmGate = useCallback(() => {
    const runner = gate?.runner
    setGate(null)
    if (runner) startRunner(runner)
  }, [gate, startRunner])

  const advisories = result?.advisories ?? []
  const verified = result?.verified_advisories ?? []
  const traces = result?.provenance_traces ?? []
  // The finished result always wins; `live` only fills the gap during a run.
  const cvEvent = result?.cv_event ?? live.cv_event
  const impact = result?.impact_prediction ?? live.impact_prediction

  /* Joined on industry, and named for it.

     Not a shortcut — the two sides use different id spaces. advisories[] carries
     a bare UUID; verified_advisories[] and provenance_traces[] carry
     "adv_{storm}_{industry}_{hash}". They never compare equal, so industry is
     the only key that actually joins them. It holds because the pipeline emits
     one advisory per industry; if that ever changes, this join needs a real
     shared id on both sides rather than a different local fix. */
  const verifiedByIndustry = useMemo(
    () => Object.fromEntries(verified.map(v => [v.industry, v])),
    [verified]
  )

  const corrections = useMemo(
    () => verified.reduce((n, v) => n + (v.verifier?.checks ?? []).filter(c => c.status === 'blocked').length, 0),
    [verified]
  )

  const healthOk = health?.status === 'ready'

  const NAV = [
    { key: 'run', label: 'Run control', layer: '—' },
    { key: 'detection', label: 'Detection', layer: 'L1', badge: cvEvent?.scales?.G ? `G${cvEvent.scales.G}` : null },
    { key: 'impact', label: 'Impact (ML)', layer: 'L2', badge: impact ? '±' : null },
    { key: 'stream', label: 'Pipeline stream', layer: '—', badge: events.length || null },
    { key: 'advisories', label: 'Advisories', layer: 'L3', badge: advisories.length || null },
    { key: 'verifier', label: 'Verifier', layer: 'L4', badge: corrections || null, tone: corrections ? 'warn' : null },
    { key: 'provenance', label: 'Provenance', layer: 'L5', badge: traces.length || null },
    { key: 'sources', label: 'Knowledge base', layer: 'RAG' },
    { key: 'ask', label: 'Ask an agent', layer: 'RAG' },
    { key: 'health', label: 'System health', layer: '—', tone: healthOk ? null : 'bad' },
  ]

  const TITLE = {
    run: 'RUN CONTROL',
    detection: 'LAYER 1 · CV DETECTION',
    impact: 'LAYER 2 · ML IMPACT PREDICTION',
    stream: 'PIPELINE STREAM',
    advisories: 'LAYER 3 · AGENTIC ADVISORIES',
    verifier: 'LAYER 4 · DETERMINISTIC VERIFIER',
    provenance: 'PROVENANCE TRACE',
    sources: 'KNOWLEDGE BASE',
    ask: 'ASK AN AGENT',
    health: 'SYSTEM HEALTH',
  }

  return (
    <div className="console">
      <aside className="console-nav" aria-label="console sections">
        <div className="console-brand">
          <Link to="/">HELIOOPS</Link>
          <div className="console-brand-sub muted">ADVISORY CONSOLE</div>
        </div>

        <nav className="nav-list">
          {NAV.map(item => (
            <button
              key={item.key}
              className={`nav-item${panel === item.key ? ' is-active' : ''}`}
              onClick={() => setPanel(item.key)}
              aria-current={panel === item.key ? 'page' : undefined}
            >
              <span className="nav-layer">{item.layer}</span>
              <span className="nav-label">{item.label}</span>
              {item.badge != null && (
                <span className={`nav-badge${item.tone ? ` is-${item.tone}` : ''}`}>{item.badge}</span>
              )}
              {item.tone === 'bad' && item.badge == null && <span className="nav-dot is-bad" />}
            </button>
          ))}
        </nav>

        <div className="console-foot">
          <div className="storm-active">
            <span className="col-head">ACTIVE STORM</span>
            <div className="storm-active-id">{stormId || '—'}</div>
          </div>
          <div className="console-status">
            <span className={`nav-dot is-${healthOk ? 'ok' : 'bad'}`} />
            <span className="small muted">api {health?.status ?? '…'}</span>
          </div>
          {busy && <div className="small running-note">run in progress · {events.length} events</div>}
        </div>
      </aside>

      <main className="console-main">
        <header className="panel-head">
          <h1>{TITLE[panel]}</h1>
          <div className="panel-head-meta">
            {/* Reachable from every panel, not just the one you started from —
                a run auto-opens the stream, and that is exactly where you are
                standing when you decide 80 seconds was a mistake. */}
            {busy && (
              <>
                <Pill tone="warn">running</Pill>
                <button className="btn btn-stop btn-small" onClick={cancelRun}>
                  Stop
                </button>
              </>
            )}
            {stormId && <span className="small muted">{stormId}</span>}
          </div>
        </header>

        {error && <div className="banner banner-bad">{error}</div>}
        {result?.errors?.length > 0 && panel !== 'run' && (
          <div className="banner banner-warn">pipeline notes: {result.errors.join(' · ')}</div>
        )}

        <div className="panel-body">
          {panel === 'run' && (
            <RunPanel
              storms={storms}
              completed={completed}
              stormId={stormId}
              setStormId={setStormId}
              busy={busy}
              gate={gate}
              result={result}
              onRun={requestRun}
              onCancelRun={cancelRun}
              onConfirmGate={confirmGate}
              onCancelGate={() => setGate(null)}
            />
          )}

          {panel === 'detection' && <DetectionPanel cvEvent={cvEvent} />}
          {panel === 'impact' && <ImpactPanel prediction={impact} />}
          {panel === 'stream' && <StreamLog events={events} startedAt={startedAt} />}

          {panel === 'advisories' &&
            (advisories.length === 0 ? (
              <Empty>
                No advisories yet. A run takes roughly 65–80s: four agents each do
                a RAG lookup, a generation pass, and a hallucination self-check on
                a second model.
              </Empty>
            ) : (
              advisories.map(a => (
                <AdvisoryCard key={a.advisory_id} advisory={a} verified={verifiedByIndustry[a.industry]} />
              ))
            ))}

          {panel === 'verifier' && <VerifierPanel verified={verified} />}
          {panel === 'provenance' && <ProvenancePanel traces={traces} verified={verified} />}
          {panel === 'sources' && <SourcesPanel />}

          {panel === 'ask' && (
            <>
              <div className="panel-lede">
                Each agent answers from the rulebooks it retrieves, and says so
                when the knowledge base does not cover the question. Runs on a
                separate model to the pipeline, so asking can never starve a run
                of its token budget.
              </div>
              <div className="ask-industry">
                {INDUSTRIES.map(i => (
                  <button
                    key={i}
                    className={`btn${askIndustry === i ? ' btn-primary' : ''}`}
                    onClick={() => setAskIndustry(i)}
                  >
                    {i}
                  </button>
                ))}
              </div>
              {/* Remount per industry so the history belongs to the agent it came from. */}
              <AskBox key={askIndustry} industry={askIndustry} Citation={Citation} />
            </>
          )}

          {panel === 'health' && (
            <>
              <div className="panel-lede">
                Polled every 15 seconds. <code>/health/ready</code> answers 503
                with the same body when degraded, so a failing dependency shows
                as a red check rather than as an unreachable API.
              </div>
              <div className="health-grid">
                <Pill tone={healthOk ? 'ok' : 'bad'}>api: {health?.status ?? 'unknown'}</Pill>
                {health?.checks &&
                  Object.entries(health.checks).map(([k, v]) => (
                    <Pill key={k} tone={v ? 'ok' : 'bad'}>
                      {k}
                    </Pill>
                  ))}
              </div>
              {!health?.checks && <Empty>No per-dependency detail in this response.</Empty>}
            </>
          )}
        </div>
      </main>
    </div>
  )
}
