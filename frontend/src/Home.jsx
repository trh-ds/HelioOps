import { useCallback, useEffect, useState } from 'react'
import { GLYPHS, INDUSTRIES, KP, wrap } from './data.js'
import './home.css'

const DEFAULT_CAPTION =
  'Real-time space weather advisories for aviation, power grid, maritime and telecom.'

export default function Home({ caption = DEFAULT_CAPTION }) {
  const [i, setI] = useState(0)
  const [dir, setDir] = useState(1)
  const [g, setG] = useState(4)

  const step = useCallback(d => {
    setDir(d)
    setI(v => wrap(v, d))
  }, [])

  useEffect(() => {
    const key = e => {
      if (e.key === 'ArrowRight') step(1)
      else if (e.key === 'ArrowLeft') step(-1)
      else if (e.key >= '1' && e.key <= '5') setG(+e.key)
    }
    window.addEventListener('keydown', key)
    return () => window.removeEventListener('keydown', key)
  }, [step])

  const cur = INDUSTRIES[i]
  const prev = INDUSTRIES[wrap(i, -1)]
  const next = INDUSTRIES[wrap(i, 1)]

  return (
    <div className="home-stage">
      <div className="frame">
        <div className="globe-layer">
          <helio-globe industry={cur.key} g-scale={String(g)} mode="hero" />
        </div>

        <div className="veil veil-glow" />
        <div className="veil veil-vignette" />

        <div className="ring ring-solid" />
        <div className="ring ring-dashed" />

        <div className="tick tick-tl" />
        <div className="tick tick-tr" />
        <div className="tick tick-bl" />
        <div className="tick tick-br" />

        <div className="panel">

          <div className="body" style={{ '--dir': dir }}>
            <div className="glyphs" aria-hidden="true">
              {GLYPHS.map((gl, n) => (
                <span key={n} style={{ left: gl.l, top: gl.t, fontSize: gl.size }}>
                  {gl.c}
                </span>
              ))}
            </div>

            <div className="caret caret-1" />
            <div className="caret caret-2" />
            <div className="caret caret-3" />

            <div className="counter">
              <span className="counter-n swap" key={i}>
                {String(i + 1).padStart(2, '0')}
              </span>
              <span className="counter-total">/{String(INDUSTRIES.length).padStart(2, '0')}</span>
            </div>

            <div className="status swap" key={`s${i}`}>
              <div className="status-title">{cur.status}</div>
              <div className="status-tag">{cur.tagline}</div>
              <div className="status-hatch" />
              <div className="status-rule" />
            </div>

            <div className="chips" key={`c${i}`}>
              {cur.chips.map((text, n) => (
                <div className="chip swap" key={text} style={{ '--n': n }}>
                  <span className="chip-dot" />
                  <span className="chip-text">{text}</span>
                </div>
              ))}
            </div>

            <div className="l1">
              <div className="l1-dot" />
              <div className="l1-line" />
              <div className="l1-label">L1 · DSCOVR</div>
            </div>

            <div className="pager">
              <button type="button" onClick={() => step(-1)} aria-label={`Previous industry: ${prev.name}`}>
                <span className="pager-name swap" key={`p${i}`}>
                  {prev.name}
                </span>
                <span className="pager-hatch" />
                <span className="pager-arrow">❮❮</span>
                <span className="pager-tail-l" />
              </button>
              <button type="button" onClick={() => step(1)} aria-label={`Next industry: ${next.name}`}>
                <span className="pager-tail-r" />
                <span className="pager-arrow">❯❯</span>
                <span className="pager-hatch" />
                <span className="pager-name swap" key={`n${i}`}>
                  {next.name}
                </span>
              </button>
            </div>

            <div className="title">
              <div className="title-bar">
                <h1 className="title-name" key={`t${i}`} aria-label={cur.name}>
                  <span className="title-wipe" aria-hidden="true" />
                  {[...cur.name].map((ch, n) => (
                    <span key={n} className="title-char" style={{ '--n': n }} aria-hidden="true">
                      {ch}
                    </span>
                  ))}
                </h1>
                <div className="title-hatch" />
              </div>
              <div className="title-meta">
                <span>INDUSTRY AGENT</span>
                <span className="title-meta-rule" />
                <span className="title-source swap" key={`src${i}`}>
                  {cur.source}
                </span>
              </div>
            </div>

            <div className="blurb swap" key={`b${i}`}>
              <div className="blurb-card">
                <strong>{cur.lede}</strong> {cur.rest}
              </div>
              <div className="blurb-hatch" />
            </div>

            <div className="scroll-hint" aria-hidden="true">
              ⌄
            </div>
          </div>

          <div className="footer">
            <div className="footer-left">
              <span>HELIOOPS</span>
              <span className="sep">/</span>
              <span>LAYER 3 ADVISORY SURFACE</span>
            </div>
            <div className="footer-right">
              <div className="footer-hatch" />
              <div className="footer-caption">{caption}</div>
            </div>
          </div>
        </div>

        <div className="storm">
          <span className="storm-label">STORM</span>
          <div className="storm-segs">
            {[1, 2, 3, 4, 5].map(v => (
              <button
                key={v}
                type="button"
                className={`storm-seg${v <= g ? ' on' : ''}`}
                onClick={() => setG(v)}
                aria-label={`Set storm level G${v}`}
                aria-pressed={v === g}
              />
            ))}
          </div>
          <span className="storm-g">G{g}</span>
          <span className="storm-kp">Kp {KP[g]}</span>
        </div>
      </div>
    </div>
  )
}
