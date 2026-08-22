import { GAPS, IMPACT_ROWS, SIGNALS } from './data.js'
import PageShell from './PageShell.jsx'
import './pages.css'

export default function Problem({ showSignals = true }) {
  return (
    <PageShell
      industry="grid"
      gscale={5}
      glow="radial-gradient(110% 80% at 76% 8%, rgba(150,66,58,.26) 0%, rgba(0,0,0,0) 58%)"
    >
      <header className="page-head">
        <div className="page-num">
          <b>03</b>
          <i>/04</i>
        </div>
        <div className="page-head-text">
          <div className="eyebrow">THE PROBLEM</div>
          <h1 className="page-title">The signal is free. The last mile does not exist.</h1>
          <p className="page-lede">
            When the Sun throws a coronal mass ejection at Earth, four industries lose capability
            within hours. NOAA alerts, DONKI kinematics, GOES flare data and DSCOVR solar wind are
            all public and all free. What nobody ships is the step between a measurement and an
            order an operator can act on at 3am.
          </p>
        </div>
      </header>

      <section className="section">
        <div className="section-head">
          <span className="section-no">3.1</span>
          <h2 className="section-h">Four gaps between data and decision</h2>
          <span className="rule-hatch" />
        </div>
        <div className="hairline-grid gaps">
          {GAPS.map(p => (
            <div className="gap" key={p.n}>
              <div className="gap-n">{p.n}</div>
              <div className="gap-title">{p.title}</div>
              <div className="gap-body">{p.body}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="section">
        <div className="section-head">
          <span className="section-no">3.2</span>
          <h2 className="section-h">What breaks, and what it costs</h2>
          <span className="rule-hatch" />
        </div>
        <div className="impact-head impact-cols">
          <div>INDUSTRY</div>
          <div>WHAT BREAKS</div>
          <div>CONSEQUENCE</div>
          <div>AT G4</div>
        </div>
        <div className="hairline-grid impact-body">
          {IMPACT_ROWS.map(r => (
            <div className="impact-row impact-cols" key={r.name}>
              <div className="impact-name">{r.name}</div>
              <div className="impact-cell">{r.breaks}</div>
              <div className="impact-cell">{r.consequence}</div>
              <div className="impact-sev" style={{ color: r.color }}>
                {r.sev}
              </div>
            </div>
          ))}
        </div>
        <p className="section-note mono">
          Severity is routed by a hard-coded G-scale matrix. At G5 all four read CRITICAL.
        </p>
      </section>

      {showSignals && (
        <section className="section">
          <div className="section-head">
            <span className="section-no">3.3</span>
            <h2 className="section-h">The raw signal that already exists</h2>
            <span className="rule-hatch" />
          </div>
          <div className="signals">
            {SIGNALS.map(s => (
              <div className="signal" key={s.src}>
                <div className="signal-src">{s.src}</div>
                <div className="signal-gives">{s.gives}</div>
                <div className="signal-note">{s.note}</div>
              </div>
            ))}
          </div>
          <div className="callout">
            <div className="callout-title">
              A wrong HF frequency in an aviation advisory is not an embarrassing hallucination. It
              is a safety incident.
            </div>
            <div className="callout-body">
              That is the reason the platform exists in this shape: regulated operators cannot act
              on an output they cannot trace back to a cited procedure and a measured input, and
              they cannot accept a number a language model invented.
            </div>
          </div>
        </section>
      )}
    </PageShell>
  )
}
