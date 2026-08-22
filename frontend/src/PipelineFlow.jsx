import { STAGES } from './data.js'

/* The pipeline as a diagram rather than five paragraphs.

   A signal enters at the Sun and leaves as an operator instruction, and the
   thing worth showing is that it only ever moves one way through five fixed
   stages. So: one rail, five nodes, and a pulse that runs the rail on a loop.
   The loop is the point - a storm feed never stops arriving.

   Pure CSS animation, no timers and no requestAnimationFrame: the browser
   compositor owns it, so it costs nothing while the operator reads, and it
   stops dead under prefers-reduced-motion.

   Colour follows the page: violet for the deterministic stages, amber for the
   verifier (the one that can rewrite an answer), green at the outlet. */
export default function PipelineFlow() {
  return (
    <div className="flow" aria-hidden="true">
      <div className="flow-rail">
        <span className="flow-pulse" />
        <span className="flow-pulse flow-pulse-2" />
      </div>

      <ol className="flow-nodes">
        <li className="flow-node flow-node-src">
          <span className="flow-dot" />
          <span className="flow-cap">SOLAR INPUT</span>
          <span className="flow-sub">CCOR-1 · LASCO · DONKI · XRS · L1</span>
        </li>

        {STAGES.map((s, i) => (
          <li
            className={`flow-node${s.n === '04' ? ' is-verifier' : ''}`}
            key={s.n}
            style={{ '--i': i + 1 }}
          >
            <span className="flow-dot" />
            <span className="flow-n">{s.n}</span>
            <span className="flow-cap">{s.title}</span>
            <span className="flow-sub">{s.out.replace(/^→\s*/, '')}</span>
          </li>
        ))}

        <li className="flow-node flow-node-out">
          <span className="flow-dot" />
          <span className="flow-cap">OPERATOR</span>
          <span className="flow-sub">cited · verified · auditable</span>
        </li>
      </ol>

      <div className="flow-trace">
        <span className="flow-trace-label">PROVENANCE</span>
        {['raw_data', 'detection', 'impact', 'retrieval', 'verifier', 'output'].map((t, i) => (
          <span className="flow-trace-step" key={t} style={{ '--i': i }}>
            {t}
          </span>
        ))}
      </div>
    </div>
  )
}
