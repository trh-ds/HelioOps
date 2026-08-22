/* Pure helpers for the console panels.

   Same reasoning as preflight.js: the only arithmetic and ordering logic in the
   new panels lives out here so src/data.test.mjs can assert it with plain node
   asserts — no DOM, no renderer, no test framework. */

/** The chain every advisory claims to carry, in order. */
export const PROVENANCE_STEPS = [
  'raw_data',
  'detection',
  'impact',
  'retrieval',
  'verifier',
  'output',
]

const STEP_LABEL = {
  raw_data: 'RAW DATA',
  detection: 'DETECTION',
  impact: 'IMPACT',
  retrieval: 'RETRIEVAL',
  verifier: 'VERIFIER',
  output: 'OUTPUT',
}

export const stepLabel = step => STEP_LABEL[step] ?? String(step).replace(/_/g, ' ').toUpperCase()

/**
 * Normalise a ProvenanceTrace into the six canonical steps.
 *
 * A missing step is rendered as missing rather than skipped — "5 of 6" is a
 * finding, and a chain that silently drops a link looks complete when it isn't.
 * Steps the backend emits outside the canonical six are appended rather than
 * discarded, so a future 7th step is visible the day it ships.
 */
export function chainSteps(trace) {
  const chain = Array.isArray(trace?.chain) ? trace.chain : []
  const byStep = new Map(chain.map(s => [s.step, s]))

  const canonical = PROVENANCE_STEPS.map(step => {
    const s = byStep.get(step)
    return {
      step,
      present: s != null,
      ref: s?.ref ?? null,
      confidence: s?.confidence ?? null,
      ci_level: s?.ci_level ?? null,
    }
  })

  const extra = chain
    .filter(s => !PROVENANCE_STEPS.includes(s.step))
    .map(s => ({
      step: s.step,
      present: true,
      extra: true,
      ref: s.ref ?? null,
      confidence: s.confidence ?? null,
      ci_level: s.ci_level ?? null,
    }))

  return {
    steps: [...canonical, ...extra],
    present: canonical.filter(s => s.present).length,
    total: PROVENANCE_STEPS.length,
  }
}

/**
 * Geometry for a quantile interval bar: q025 ─ q500 ─ q975 over a padded domain.
 *
 * Returns percentages so the bar is pure CSS. `null` for anything non-numeric —
 * a panel that cannot draw the interval must say so rather than render a bar
 * pinned at zero, which reads as a real measurement of zero.
 *
 * The three values are sorted rather than trusted: inference.py already enforces
 * monotonicity, but quantile crossing is a real failure mode of independently
 * trained quantile models and a crossed pair must not invert the bar.
 */
export function intervalGeometry(low, med, high, { min = null, max = null } = {}) {
  // typeof, not Number(): Number(null) and Number('') are both 0, so a missing
  // quantile would coerce into a bar drawn at a real, measured zero.
  const nums = [low, med, high]
  if (nums.some(n => typeof n !== 'number' || !Number.isFinite(n))) return null

  const [lo, mid, hi] = [...nums].sort((a, b) => a - b)

  const span = hi - lo
  const pad = span > 0 ? span * 0.2 : Math.max(Math.abs(hi) * 0.1, 1)
  const d0 = min ?? lo - pad
  const d1 = max ?? hi + pad
  const width = d1 - d0 || 1
  const at = v => ((v - d0) / width) * 100

  return {
    lo,
    med: mid,
    hi,
    domain: [d0, d1],
    leftPct: at(lo),
    widthPct: at(hi) - at(lo),
    medPct: at(mid),
  }
}

/**
 * mm:ss since the run started — the stream's clock.
 *
 * Elapsed rather than wall time on purpose: the question a judge asks about an
 * 80-second run is "where did the 80 seconds go", and a wall clock makes you do
 * the subtraction yourself. Negative (an event stamped before the start) clamps
 * to zero rather than rendering "-0:03".
 */
export function elapsed(startMs, atMs) {
  if (!Number.isFinite(startMs) || !Number.isFinite(atMs)) return ''
  const s = Math.max(0, Math.round((atMs - startMs) / 1000))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}
