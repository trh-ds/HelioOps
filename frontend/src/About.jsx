import { ABOUT_STATS, BETS, CAVEATS, REAL, STAGES, TEAM } from './data.js'
import PageShell from './PageShell.jsx'
import PipelineFlow from './PipelineFlow.jsx'
import './pages.css'

export default function About({ showTeam = true }) {
  return (
    <PageShell
      industry="aviation"
      gscale={4}
      glow="radial-gradient(120% 90% at 78% 10%, rgba(96,70,190,.30) 0%, rgba(0,0,0,0) 60%)"
    >
      <header className="page-head">
        <div className="page-num">
          <b>02</b>
          <i>/04</i>
        </div>
        <div className="page-head-text">
          <div className="eyebrow">ABOUT THE PROJECT</div>
          <h1 className="page-title">
            A space weather platform that hands operators verified orders, not alerts
          </h1>
          <p className="page-lede">
            HelioOps watches the Sun, predicts what a solar storm will do to critical
            infrastructure, and produces regulator-cited, machine-verified action lists for four
            industries — with a full audit trail from raw coronagraph imagery to the final
            instruction.
          </p>
          <div className="page-stats">
            {ABOUT_STATS.map(s => (
              <span key={s}>{s}</span>
            ))}
          </div>
        </div>
      </header>

      <section className="section" id="pipeline">
        <div className="section-head">
          <span className="section-no">2.1</span>
          <h2 className="section-h">The five-stage pipeline</h2>
          <span className="rule-hatch" />
        </div>
        <PipelineFlow />
        <div className="hairline-grid stages">
          {STAGES.map(s => (
            <div className="stage" key={s.n}>
              <div className="stage-top">
                <span className="stage-n">{s.n}</span>
                <span className="stage-dot" />
              </div>
              <div className="stage-title">{s.title}</div>
              <div className="stage-body">{s.body}</div>
              <div className="stage-out">{s.out}</div>
            </div>
          ))}
        </div>
        <p className="section-note">
          One direction, five fixed stages, and nothing downstream can reach back. Every advisory
          that arrives carries the trace above it, so any instruction can be walked back to the
          frame it came from.
        </p>
      </section>

      <section className="section">
        <div className="section-head">
          <span className="section-no">2.2</span>
          <h2 className="section-h">Four decisions that define it</h2>
          <span className="rule-hatch" />
        </div>
        <div className="bets">
          {BETS.map(b => (
            <div className="bet" key={b.tag}>
              <div className="bet-tag">{b.tag}</div>
              <div className="bet-title">{b.title}</div>
              <div className="bet-body">{b.body}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="section" id="maturity">
        <div className="section-head">
          <span className="section-no">2.3</span>
          <h2 className="section-h">Current maturity, stated plainly</h2>
          <span className="rule-hatch" />
        </div>
        <div className="hairline-grid maturity">
          <div className="maturity-col good">
            <div className="maturity-head good">REAL AND RUNNING</div>
            {REAL.map(text => (
              <div className="maturity-item" key={text}>
                <span className="dash">—</span>
                <span>{text}</span>
              </div>
            ))}
          </div>
          <div className="maturity-col warn">
            <div className="maturity-head warn">CAVEATS WORTH KNOWING</div>
            {CAVEATS.map(text => (
              <div className="maturity-item" key={text}>
                <span className="dash">—</span>
                <span>{text}</span>
              </div>
            ))}
          </div>
        </div>
        <p className="section-note mono">Production-shaped, not yet production-proven.</p>
      </section>

      {showTeam && (
        <section className="section">
          <div className="section-head">
            <span className="section-no">2.4</span>
            <h2 className="section-h">The Fantastic 4</h2>
            <span className="rule-hatch" />
          </div>
          <div className="team">
            {TEAM.map(t => (
              <div className="team-card" key={t.name}>
                <div className="team-name">{t.name}</div>
                <div className="team-layer">{t.layer}</div>
                <div className="team-role">{t.role}</div>
              </div>
            ))}
          </div>
        </section>
      )}
    </PageShell>
  )
}
