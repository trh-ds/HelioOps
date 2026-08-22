import { FOOTER_RULEBOOKS, FOOTER_SOURCES } from './data.js'
import { Link } from './router.jsx'
import './shell.css'

function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="site-footer-grid">
        <div>
          <div className="brand">HELIOOPS</div>
          <div className="brand-hatch" />
          <div className="brand-blurb">
            Real-time space weather operations for aviation, power grid, maritime and telecom. LLMs
            generate prose; deterministic code owns every safety-critical number.
          </div>
        </div>
        <div>
          <div className="col-head">PAGES</div>
          <div className="col-list">
            <Link to="/">Main</Link>
            <Link to="/about">About</Link>
            <Link to="/problem">Problem</Link>
            <Link to="/industries">Industries</Link>
          </div>
        </div>
        <div>
          <div className="col-head">DATA SOURCES</div>
          <div className="col-list muted">
            {FOOTER_SOURCES.map(s => (
              <span key={s}>{s}</span>
            ))}
          </div>
        </div>
        <div>
          <div className="col-head">RULEBOOKS IN RAG</div>
          <div className="col-list muted">
            {FOOTER_RULEBOOKS.map(s => (
              <span key={s}>{s}</span>
            ))}
          </div>
        </div>
      </div>
      <div className="site-footer-rule">
        <div className="colophon">
          HELIOOPS <span className="sep">/</span> LAYER 4 · STUDENT PROJECT · 8–14 JUNE 2026
        </div>
        <div className="colophon-hatch" />
        <div className="colophon-note">
          Detection is reproducible. Severity is a lookup table. The verifier has the last word.
        </div>
      </div>
    </footer>
  )
}

/** Ambient globe + veils + nav + footer: the frame every content page sits in. */
export default function PageShell({ industry, gscale = 4, glow, children }) {
  return (
    <div className="page">
      <div className="page-globe">
        <helio-globe industry={industry} g-scale={String(gscale)} mode="ambient" />
      </div>
      <div className="page-fade" />
      <div className="page-glow" style={{ '--page-glow': glow }} />

      <main className="page-body">{children}</main>

      <SiteFooter />
    </div>
  )
}
