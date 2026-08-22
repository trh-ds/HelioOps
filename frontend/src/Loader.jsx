import { BOOT_BEATS } from './data.js'
import './loader.css'

/* Boot sequence. Every timing lives in loader.css; BOOT_MS in main.jsx is the
   one number that has to agree with it — it decides when this unmounts. */
export default function Loader() {
  return (
    <div className="loader" role="status" aria-label="Loading HelioOps">
      <div className="loader-veil" aria-hidden="true" />
      <div className="loader-flare" aria-hidden="true" />
      <div className="loader-scan" aria-hidden="true" />

      <div className="loader-tag" aria-hidden="true">
        HELIOOPS <span>/</span> BOOT SEQUENCE
      </div>

      <div className="loader-beats" aria-hidden="true">
        {BOOT_BEATS.map((b, i) => (
          <div
            key={b.line}
            className={i === BOOT_BEATS.length - 1 ? 'loader-beat is-final' : 'loader-beat'}
            style={{ '--i': i }}
          >
            <div className="loader-line">{b.line}</div>
            <div className="loader-sub">{b.sub}</div>
          </div>
        ))}
      </div>

      <div className="loader-bar" aria-hidden="true">
        <span />
      </div>
      <div className="loader-skip" aria-hidden="true">
        CLICK OR PRESS ANY KEY TO SKIP
      </div>
    </div>
  )
}
