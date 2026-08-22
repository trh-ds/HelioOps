import { useCallback, useEffect, useRef, useState } from 'react'
import PageShell from './PageShell.jsx'
import { getHealth, getPreflight, getResult, getStorms, runPipeline, streamPipeline } from './api.js'
import './dashboard.css'

/* The operator-facing surface for the advisory layer.

   Deliberately plain: this exists to make the pipeline observable — what the
   agents retrieved, what they wrote, which guardrail fired, and what the
   deterministic verifier changed before dispatch. Styling is meant to be
   replaced; the data contract is the part worth keeping. */

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

const pct = n => `${Math.round((n ?? 0) * 100)}%`

function Pill({ tone = 'info', children, title }) {
  return (
    <span className={`pill pill-${tone}`} title={title}>
      {children}
    </span>
  )
}

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

function StreamLog({ events }) {
  const endRef = useRef(null)
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'nearest' })
  }, [events.length])

  if (!events.length) {
    return <div className="muted small">No run yet. Press “Run live” to watch the agents work.</div>
  }

  return (
    <div className="streamlog">
      {events.map((e, i) => (
        <div key={i} className={`streamline tone-${toneOf(e)}`}>
          <span className="streamline-tag">{e.industry ?? e.stage ?? e.event.split('.')[0]}</span>
          <span className="streamline-step">{e.step ?? e.event}</span>
          <span className="streamline-msg">{describe(e)}</span>
        </div>
      ))}
      <div ref={endRef} />
    </div>
  )
}

/* ---------- Advisory ---------- */

function AdvisoryCard({ advisory, verified }) {
  const [open, setOpen] = useState(true)
  const flags = advisory.safety_flags ?? []
  const vstatus = verified?.verifier?.status
  const checks = verified?.verifier?.checks ?? []
  const corrections = checks.filter(c => c.status === 'blocked')

  return (
    <section className="adv">
      <header className="adv-head" onClick={() => setOpen(o => !o)}>
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
                  <span className="act-cite" title="source_ref — must resolve to a retrieved chunk">
                    {a.source_ref}
                  </span>
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
        </div>
      )}
    </section>
  )
}

/* ---------- Pre-flight ---------- */

const PREFLIGHT_TONE = { block: 'bad', warn: 'warn', info: 'info' }

/* Progressive disclosure before the 65-80s commit: a one-line summary always,
   the individual findings only behind <details>. Never hard-blocks — even a
   `block` finding leaves "Run anyway" enabled; its detail explains the 429. */
function PreflightPanel({ gate, onConfirm, onCancel }) {
  if (gate.phase === 'loading') {
    return (
      <div className="preflight">
        <span className="col-head">PRE-FLIGHT</span>
        <span className="muted small">checking cached inputs, conflicts and quota…</span>
      </div>
    )
  }

  const { findings, estimated_duration_s } = gate.data
  const count = sev => findings.filter(f => f.severity === sev).length
  const serious = count('block') + count('warn')

  return (
    <div className="preflight">
      <div className="preflight-summary">
        <span className="col-head">PRE-FLIGHT</span>
        {['block', 'warn', 'info'].map(
          sev =>
            count(sev) > 0 && (
              <Pill key={sev} tone={PREFLIGHT_TONE[sev]}>
                {count(sev)} {sev}
              </Pill>
            )
        )}
        {findings.length === 0 && <Pill tone="ok">no findings</Pill>}
        <span className="muted small">est ~{estimated_duration_s}s</span>
        <span className="preflight-actions">
          <button className="btn btn-primary" onClick={onConfirm}>
            {serious > 0 ? 'Run anyway' : 'Run'}
          </button>
          <button className="btn" onClick={onCancel}>
            Cancel
          </button>
        </span>
      </div>
      {findings.length > 0 && (
        <details className="preflight-findings">
          <summary className="small muted">
            show {findings.length} finding{findings.length === 1 ? '' : 's'}
          </summary>
          <ul>
            {findings.map(f => (
              <li key={f.id}>
                <Pill tone={PREFLIGHT_TONE[f.severity] ?? 'info'}>{f.severity}</Pill>{' '}
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

/* ---------- Page ---------- */

export default function Dashboard() {
  const [storms, setStorms] = useState([])
  const [stormId, setStormId] = useState('')
  const [health, setHealth] = useState(null)
  const [events, setEvents] = useState([])
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  // Pre-flight gate: null | {phase:'loading'|'confirm', runner:'live'|'batch', data?}
  const [gate, setGate] = useState(null)
  const closeRef = useRef(null)

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth({ status: 'unreachable' }))
    getStorms()
      .then(d => {
        setStorms(d.available_storms ?? [])
        setStormId(prev => prev || d.available_storms?.[0] || '')
      })
      .catch(e => setError(String(e.message ?? e)))
  }, [])

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
    closeRef.current?.()
    closeRef.current = streamPipeline(stormId, {
      onEvent: e => {
        setEvents(prev => [...prev, e])
        if (e.event === 'error') setError(e.message)
      },
      onClose: () => {
        setBusy(false)
        // The stream carries advisories, but the persisted result also has the
        // verifier output and provenance, which only exist after the run.
        getResult(stormId).then(setResult).catch(() => {})
      },
      onError: e => {
        setError(String(e.message ?? e))
        setBusy(false)
      }
    })
  }, [stormId, busy])

  const startBatch = useCallback(async () => {
    if (!stormId || busy) return
    setBusy(true)
    setError(null)
    setEvents([])
    try {
      setResult(await runPipeline(stormId))
    } catch (e) {
      setError(String(e.message ?? e))
    } finally {
      setBusy(false)
    }
  }, [stormId, busy])

  const startRunner = useCallback(
    runner => (runner === 'live' ? startLive() : startBatch()),
    [startLive, startBatch]
  )

  // Every run goes through the gate: preflight first, confirm, then start.
  // If preflight itself fails, start directly — the gate never breaks the demo.
  const requestRun = useCallback(
    runner => {
      if (!stormId || busy || gate) return
      setGate({ phase: 'loading', runner })
      getPreflight(stormId)
        .then(data => setGate({ phase: 'confirm', runner, data }))
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
  const verifiedById = Object.fromEntries(
    (result?.verified_advisories ?? []).map(v => [v.industry, v])
  )

  return (
    <PageShell industry="grid" gscale={5} glow="rgba(120,160,255,.10)">
      <div className="dash">
        <header className="dash-head">
          <h1>ADVISORY CONSOLE</h1>
          <div className="dash-sub muted">
            Layer 3 · four industry agents, RAG-grounded, deterministically verified
          </div>
        </header>

        <div className="dash-controls">
          <label className="ctl">
            <span className="col-head">STORM</span>
            <select
              value={stormId}
              onChange={e => setStormId(e.target.value)}
              disabled={busy || gate != null}
            >
              {storms.length === 0 && <option value="">(backend unreachable)</option>}
              {storms.map(s => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>

          <button
            className="btn btn-primary"
            onClick={() => requestRun('live')}
            disabled={busy || !stormId || gate != null}
          >
            {busy ? 'Running…' : 'Run live (WebSocket)'}
          </button>
          <button
            className="btn"
            onClick={() => requestRun('batch')}
            disabled={busy || !stormId || gate != null}
          >
            Run batch (REST)
          </button>

          <div className="health">
            {health && (
              <>
                <Pill tone={health.status === 'ready' ? 'ok' : 'bad'}>api: {health.status}</Pill>
                {health.checks &&
                  Object.entries(health.checks).map(([k, v]) => (
                    <Pill key={k} tone={v ? 'ok' : 'bad'}>
                      {k}
                    </Pill>
                  ))}
              </>
            )}
          </div>
        </div>

        {gate && <PreflightPanel gate={gate} onConfirm={confirmGate} onCancel={() => setGate(null)} />}

        {error && <div className="banner banner-bad">{error}</div>}

        <div className="dash-grid">
          <div className="dash-col">
            <div className="col-head">PIPELINE STREAM</div>
            <StreamLog events={events} />
          </div>

          <div className="dash-col">
            <div className="col-head">
              ADVISORIES {advisories.length > 0 && `(${advisories.length})`}
            </div>
            {advisories.length === 0 ? (
              <div className="muted small">
                Nothing yet. A run takes roughly 20–70s: four agents each do a RAG lookup, a
                generation pass, and a hallucination self-check on a second model.
              </div>
            ) : (
              advisories.map(a => (
                <AdvisoryCard key={a.advisory_id} advisory={a} verified={verifiedById[a.industry]} />
              ))
            )}

            {result?.errors?.length > 0 && (
              <div className="banner banner-warn">
                pipeline notes: {result.errors.join(' · ')}
              </div>
            )}
          </div>
        </div>

        {result?.impact_prediction && (
          <div className="dash-col">
            <div className="col-head">ML IMPACT PREDICTION</div>
            <pre className="rawjson">{JSON.stringify(result.impact_prediction, null, 2)}</pre>
          </div>
        )}
      </div>
    </PageShell>
  )
}
