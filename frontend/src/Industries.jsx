import { useState } from 'react'
import { AUDIENCES, COMPARE, COMPARE_HEAD, COSTS, IND_DETAIL } from './data.js'
import PageShell from './PageShell.jsx'
import './pages.css'

export default function Industries({ showComparison = true }) {
  const [focus, setFocus] = useState('aviation')

  return (
    <PageShell
      industry={focus}
      gscale={4}
      glow="radial-gradient(110% 80% at 78% 8%, rgba(96,70,190,.28) 0%, rgba(0,0,0,0) 58%)"
    >
      <header className="page-head">
        <div className="page-num">
          <b>04</b>
          <i>/04</i>
        </div>
        <div className="page-head-text">
          <div className="eyebrow">WHO IT HELPS</div>
          <h1 className="page-title">Four industries, one screen, one cited action list each</h1>
          <p className="page-lede">
            Each industry gets a numbered action list with a time window and a cited source
            document, not a paragraph of prose to interpret under pressure. Hover an industry to
            bring it up on the globe.
          </p>
        </div>
      </header>

      <section className="section">
        <div className="section-head">
          <span className="section-no">4.1</span>
          <h2 className="section-h">What each industry gets</h2>
          <span className="rule-hatch" />
        </div>
        <div className="ind-cards">
          {IND_DETAIL.map(ind => (
            <div
              className="ind-card"
              key={ind.key}
              // focus as well as hover, so keyboard users can drive the globe too
              onMouseEnter={() => setFocus(ind.key)}
              onFocus={() => setFocus(ind.key)}
              tabIndex={0}
            >
              <div className="ind-card-top">
                <div className="ind-name">{ind.name}</div>
                <div className="ind-sev" style={{ color: ind.sevColor }}>
                  {ind.sev} AT G4
                </div>
              </div>
              <div className="ind-hatch" />
              <div className="ind-body">{ind.body}</div>
              <div className="ind-split">
                <div>
                  <div className="ind-split-head">SAVED FROM GUESSWORK</div>
                  <div className="ind-split-body">{ind.saves}</div>
                </div>
                <div>
                  <div className="ind-split-head">VERIFIER RULE</div>
                  <div className="ind-split-body">{ind.rule}</div>
                </div>
              </div>
              <div className="ind-source">
                <span className="k">SOURCE</span>
                <span className="dashline" />
                <span className="v">{ind.source}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="section">
        <div className="section-head">
          <span className="section-no">4.2</span>
          <h2 className="section-h">Resources it takes to run</h2>
          <span className="rule-hatch" />
        </div>
        <div className="hairline-grid costs">
          {COSTS.map(c => (
            <div className="cost" key={c.label}>
              <div className="cost-figure">{c.figure}</div>
              <div className="cost-label">{c.label}</div>
              <div className="cost-note">{c.note}</div>
            </div>
          ))}
        </div>
        <p className="section-note">
          The whole pipeline runs on CPU. No GPU for detection, which is a threshold algorithm; none
          for impact, where the checkpoints are under 500&nbsp;KB; none for embeddings, which use a
          384-dimension model. The only external paid dependency is the LLM, and the self-check step
          deliberately uses a lighter 8B model to stay inside free-tier rate limits.
        </p>
      </section>

      {showComparison && (
        <>
          <section className="section">
            <div className="section-head">
              <span className="section-no">4.3</span>
              <h2 className="section-h">Against the alternatives</h2>
              <span className="rule-hatch" />
            </div>
            <div className="compare-head compare-cols">
              <div />
              {COMPARE_HEAD.map(h => (
                <div key={h}>{h}</div>
              ))}
            </div>
            <div className="hairline-grid compare-body">
              {COMPARE.map(c => (
                <div className="compare-row compare-cols" key={c.row}>
                  <div>{c.row}</div>
                  <div>{c.a}</div>
                  <div>{c.b}</div>
                  <div>{c.c}</div>
                  <div>{c.d}</div>
                </div>
              ))}
            </div>
          </section>

          <section className="section">
            <div className="audiences">
              {AUDIENCES.map(a => (
                <div className="audience" key={a.who}>
                  <div className="audience-who">{a.who}</div>
                  <div className="audience-title">{a.title}</div>
                  <div className="audience-body">{a.body}</div>
                </div>
              ))}
            </div>
          </section>
        </>
      )}
    </PageShell>
  )
}
