import { useEffect, useState } from 'react'
import { citationUrl, getKbSources } from './api.js'
import { chainSteps, intervalGeometry, stepLabel } from './console.js'

/* The panels the sidebar switches between.

   Everything here renders data that already arrived in PipelineResult and was
   previously either dropped on the floor (cv_event, provenance_traces) or dumped
   as raw JSON (impact_prediction). No new endpoint, no new dependency: the bars
   and the timeline are CSS, because "three runtime dependencies" is a claim this
   project makes out loud and a chart library would end it. */

export function Pill({ tone = 'info', children, title }) {
  return (
    <span className={`pill pill-${tone}`} title={title}>
      {children}
    </span>
  )
}

/* An absent panel says why it is absent. "Nothing rendered" and "the layer did
   not run" look identical otherwise, and only one of them is a bug. */
export function Empty({ children }) {
  return <div className="panel-empty muted small">{children}</div>
}

function Stat({ label, value, unit, tone }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className={`stat-value${tone ? ` is-${tone}` : ''}`}>
        {value ?? '—'}
        {unit && value != null && <span className="stat-unit">{unit}</span>}
      </div>
    </div>
  )
}

const fmt = (n, digits = 1) => (typeof n === 'number' ? n.toFixed(digits) : null)
const clock = iso => (iso ? String(iso).replace('T', ' ').replace(/(\.\d+)?Z?$/, ' UTC') : '—')

/* ---------- Layer 1 · detection ---------- */

const SCALE_MEANING = {
  G: ['Geomagnetic storm', 'Kp-driven — grid, GPS, pipelines'],
  S: ['Solar radiation storm', 'Proton flux — polar routes, crew dose'],
  R: ['Radio blackout', 'X-ray flux — HF propagation'],
}

function ScaleTile({ letter, level }) {
  const [name, note] = SCALE_MEANING[letter] ?? ['', '']
  const tone = level >= 4 ? 'bad' : level >= 3 ? 'warn' : level >= 1 ? 'info' : 'ok'
  return (
    <div className={`scale-tile is-${tone}`}>
      <div className="scale-badge">
        {letter}
        {level ?? 0}
      </div>
      <div>
        <div className="scale-name">{name}</div>
        <div className="scale-note muted small">{note}</div>
      </div>
    </div>
  )
}

export function DetectionPanel({ cvEvent }) {
  if (!cvEvent || Object.keys(cvEvent).length === 0) {
    return (
      <Empty>
        Layer 1 has not run. Detection output appears here once a storm is
        replayed — nine deterministic threshold steps over the coronagraph frames,
        fused with the NASA physics feeds. No model weights, no RNG.
      </Empty>
    )
  }

  const { scales = {}, cme = {}, flare = {}, l1_solar_wind: l1 = {}, timeline = [] } = cvEvent

  /* Mid-run the stream carries scales and confidence only; the full StormEvent
     lands with the persisted result. Show what exists and say what is coming,
     rather than a grid of em-dashes that reads as detection having failed. */
  const partial = !cvEvent.detected_at

  return (
    <>
      <div className="panel-lede">
        {partial ? (
          <>Detection complete — kinematics, flare and L1 detail land when the run finishes.</>
        ) : (
          <>
            Detected {clock(cvEvent.detected_at)} · deterministic threshold detector,
            fused with DONKI / GOES-XRS / DSCOVR L1.
          </>
        )}
        {typeof cvEvent.confidence === 'number' && (
          <> Detection confidence <b>{Math.round(cvEvent.confidence * 100)}%</b>.</>
        )}
      </div>

      <div className="scale-row">
        {['G', 'S', 'R'].map(k => (
          <ScaleTile key={k} letter={k} level={scales[k]} />
        ))}
      </div>

      {cvEvent.noaa_alert_raw && (
        <div className="alert-raw">
          <span className="col-head">NOAA ALERT</span>
          <code>{cvEvent.noaa_alert_raw}</code>
        </div>
      )}

      <div className="panel-cols">
        {cme.detected != null && (
        <section className="subpanel">
          <div className="col-head">CORONAL MASS EJECTION</div>
          <div className="stat-grid">
            <Stat label="Speed" value={cme.speed_km_s} unit=" km/s" tone={cme.speed_km_s >= 1500 ? 'bad' : null} />
            <Stat label="Angular width" value={cme.angular_width_deg} unit="°" />
            <Stat label="Direction" value={cme.direction?.replace(/_/g, ' ')} />
            <Stat label="Confidence" value={fmt(cme.confidence, 2)} />
          </div>
          <div className="small muted">
            Source {cme.source ?? '—'} · earth arrival estimate {clock(cme.arrival_estimate)}
          </div>
          {cme.frame_path && (
            // Honest about T1-3: the stub names an annotated frame, and no such
            // PNG is committed and no route serves images. Better a stated
            // absence than a broken <img>.
            <div className="small muted frame-note">
              Annotated frame <code>{cme.frame_path}</code> is referenced by the
              detector but not served in this build.
            </div>
          )}
        </section>
        )}

        {flare.detected != null && (
        <section className="subpanel">
          <div className="col-head">SOLAR FLARE</div>
          <div className="stat-grid">
            <Stat label="Class" value={flare.class} tone={/^X/.test(flare.class ?? '') ? 'bad' : null} />
            <Stat label="R scale" value={flare.r_scale != null ? `R${flare.r_scale}` : null} />
          </div>
          <div className="small muted">
            {flare.source ?? '—'} · onset {clock(flare.onset)}
          </div>

          <div className="col-head l1-head">L1 SOLAR WIND</div>
          <div className="stat-grid">
            <Stat label="Speed" value={l1.speed_km_s} unit=" km/s" />
            <Stat label="Bz" value={l1.bz_nt} unit=" nT" tone={l1.bz_nt <= -20 ? 'bad' : null} />
            <Stat label="Lead time" value={l1.eta_minutes} unit=" min" />
          </div>
          <div className="small muted">measured {clock(l1.measured_at)}</div>
        </section>
        )}
      </div>

      {timeline.length > 0 && (
        <section className="subpanel">
          <div className="col-head">WARNING TIMELINE</div>
          <ol className="timeline">
            {timeline.map((t, i) => (
              <li key={i}>
                <span className="tl-dot" />
                <div className="tl-horizon">{String(t.horizon).replace(/_/g, ' ')}</div>
                <div className="small muted">{t.source}</div>
                <div className="small tl-time">{clock(t.t)}</div>
              </li>
            ))}
          </ol>
        </section>
      )}
    </>
  )
}

/* ---------- Layer 2 · ML impact ---------- */

/* The interval is the point. A median alone is a guess presented as a fact;
   the band is what makes it a forecast an operator can act on. */
function IntervalBar({ label, geo, unit, format, note }) {
  if (!geo) {
    return (
      <div className="interval">
        <div className="interval-label">{label}</div>
        <Empty>No interval — the model returned nothing usable for this metric.</Empty>
      </div>
    )
  }
  const f = format ?? (v => `${fmt(v)}${unit ?? ''}`)
  return (
    <div className="interval">
      <div className="interval-label">
        <span>
          {label} <span className="interval-ci">95% CI</span>
        </span>
        <span className="interval-headline">{f(geo.med)}</span>
      </div>
      <div className="interval-track">
        <div className="interval-band" style={{ left: `${geo.leftPct}%`, width: `${geo.widthPct}%` }} />
        <div className="interval-med" style={{ left: `${geo.medPct}%` }} />
      </div>
      {/* Anchored to the band, not spread across the track: a bound printed at
          the far edge of the axis reads as the axis maximum, which for a 0–1
          probability is a different number entirely. The CI label lives up in
          the heading because a narrow band leaves no room for it down here. */}
      <div className="interval-scale small muted">
        <span className="interval-bound" style={{ left: `${geo.leftPct}%` }}>{f(geo.lo)}</span>
        <span className="interval-bound" style={{ left: `${geo.leftPct + geo.widthPct}%` }}>
          {f(geo.hi)}
        </span>
      </div>
      {note && <div className="small muted">{note}</div>}
    </div>
  )
}

export function ImpactPanel({ prediction }) {
  if (!prediction) {
    return (
      <Empty>
        Layer 2 has not run. Six LightGBM quantile models (q0.025 / q0.500 /
        q0.975 across two targets) turn the detected storm into a GPS error and
        an HF blackout probability, each with a 95% interval.
      </Empty>
    )
  }

  const gps = intervalGeometry(
    prediction.gps_error_ci_low,
    prediction.gps_error_m,
    prediction.gps_error_ci_high
  )
  const hf = intervalGeometry(
    prediction.hf_blackout_ci_low,
    prediction.hf_blackout_prob,
    prediction.hf_blackout_ci_high,
    { min: 0, max: 1 }
  )

  return (
    <>
      <div className="panel-lede">
        Quantile regression, not a point estimate — the model is trained to
        predict the bounds directly, so the band is a model output rather than a
        confidence interval inferred after the fact.
      </div>

      <IntervalBar
        label="GPS L1 positioning error"
        geo={gps}
        unit=" m"
        note="Ionospheric delay at L1. Drives maritime and aviation navigation advisories."
      />
      <IntervalBar
        label="HF radio blackout probability"
        geo={hf}
        format={v => `${Math.round(v * 100)}%`}
        note="Dayside HF absorption. Drives the ICAO NAT frequency guidance the verifier then bounds."
      />

      <details className="rawdrop">
        <summary className="small muted">raw model output</summary>
        <pre className="rawjson">{JSON.stringify(prediction, null, 2)}</pre>
      </details>
    </>
  )
}

/* ---------- Layer 4 · verifier roll-up ---------- */

const VERIFIER_TONE = {
  passed: 'ok',
  passed_with_corrections: 'warn',
  blocked: 'bad',
  not_applicable: 'info',
}

export function VerifierPanel({ verified }) {
  if (!verified?.length) {
    return (
      <Empty>
        Nothing verified yet. Every numeric value an agent proposes is checked
        against the authoritative constants — ICAO NAT HF bands, GMDSS channels,
        reroute latitudes, NERC GIC thresholds — by a rule engine with no model
        in it. Unsafe values are rewritten, not merely flagged.
      </Empty>
    )
  }

  const rows = verified.flatMap(v =>
    (v.verifier?.checks ?? []).map(c => ({ ...c, industry: v.industry, advisory_id: v.advisory_id }))
  )
  const corrections = rows.filter(c => c.status === 'blocked')

  return (
    <>
      <div className="panel-lede">
        {rows.length} deterministic check{rows.length === 1 ? '' : 's'} across{' '}
        {verified.length} advisor{verified.length === 1 ? 'y' : 'ies'} ·{' '}
        <b>{corrections.length} value{corrections.length === 1 ? '' : 's'} corrected</b>.
      </div>

      <div className="vstatus-row">
        {verified.map(v => (
          <div key={v.advisory_id} className="vstatus">
            <span className="vstatus-industry">{v.industry}</span>
            <Pill tone={VERIFIER_TONE[v.verifier?.status] ?? 'info'}>
              {v.verifier?.status ?? 'unknown'}
            </Pill>
            {v.requires_human && <Pill tone="bad">requires human review</Pill>}
          </div>
        ))}
      </div>

      {rows.length === 0 ? (
        <Empty>
          No rule in the engine covers these advisories, so nothing was checked.
          That is reported as <code>not_applicable</code> rather than as a pass —
          "every check succeeded" and "there were no checks" are different claims.
        </Empty>
      ) : (
        <table className="vtable">
          <thead>
            <tr>
              <th>Industry</th>
              <th>Field</th>
              <th>Proposed</th>
              <th>Enforced</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c, i) => (
              <tr key={i} className={c.status === 'blocked' ? 'is-blocked' : ''}>
                <td className="vt-industry">{c.industry}</td>
                <td>
                  <code>{c.field}</code>
                </td>
                <td className={c.status === 'blocked' ? 'vt-rejected' : ''}>{String(c.proposed)}</td>
                <td className="vt-corrected">
                  {c.status === 'blocked' ? String(c.corrected_to) : '— unchanged'}
                </td>
                <td className="small muted">{c.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  )
}

/* ---------- Provenance ---------- */

export function ProvenancePanel({ traces, verified }) {
  if (!traces?.length) {
    return (
      <Empty>
        No traces yet. Every advisory carries a six-step chain —
        raw_data → detection → impact → retrieval → verifier → output — recording
        what each stage contributed and with what confidence.
      </Empty>
    )
  }

  /* Through verified_advisories, not advisories: traces and verified advisories
     share the "adv_{storm}_{industry}_{hash}" id space, while advisories[] uses
     a bare UUID that matches neither. */
  const industryOf = id => verified?.find(v => v.advisory_id === id)?.industry

  return (
    <>
      <div className="panel-lede">
        {traces.length} chain{traces.length === 1 ? '' : 's'} · each links an
        advisory back to the raw feed it came from. This is the audit trail a
        regulated operator has to be able to produce.
      </div>

      {traces.map(trace => {
        const { steps, present, total } = chainSteps(trace)
        return (
          <section key={trace.trace_id ?? trace.advisory_id} className="subpanel">
            <div className="prov-head">
              <span className="vstatus-industry">{industryOf(trace.advisory_id) ?? 'advisory'}</span>
              <Pill tone={present === total ? 'ok' : 'warn'}>
                {present}/{total} steps
              </Pill>
              <code className="small muted">{trace.trace_id}</code>
            </div>

            <ol className="prov-chain">
              {steps.map(s => (
                <li key={s.step} className={s.present ? '' : 'is-missing'}>
                  <span className="prov-step">{stepLabel(s.step)}</span>
                  <span className="prov-ref">{s.ref ?? 'not recorded'}</span>
                  <span className="prov-conf small muted">
                    {typeof s.confidence === 'number' && `conf ${fmt(s.confidence, 2)}`}
                    {typeof s.ci_level === 'number' && ` · ${Math.round(s.ci_level * 100)}% CI`}
                  </span>
                </li>
              ))}
            </ol>
          </section>
        )
      })}
    </>
  )
}

/* ---------- Knowledge base ---------- */

export function SourcesPanel() {
  const [sources, setSources] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    getKbSources()
      .then(d => setSources(d.sources ?? []))
      .catch(e => setError(String(e.message ?? e)))
  }, [])

  if (error) return <Empty>Knowledge base unreachable — {error}</Empty>
  if (!sources) return <Empty>Loading the document index…</Empty>
  if (!sources.length) return <Empty>No citable documents are indexed in this build.</Empty>

  return (
    <>
      <div className="panel-lede">
        {sources.length} document{sources.length === 1 ? '' : 's'} in the retrieval
        corpus. Every citation in an advisory resolves to one of these and opens
        at the cited page — a citation naming anything else is rendered as plain
        text rather than a dead link.
      </div>
      <ul className="kb-list">
        {sources.map(s => {
          const href = citationUrl(s)
          return (
            <li key={s}>
              {href ? (
                <a className="act-cite act-cite-link" href={href} target="_blank" rel="noreferrer">
                  {s}
                </a>
              ) : (
                <span className="act-cite">{s}</span>
              )}
            </li>
          )
        })}
      </ul>
    </>
  )
}
