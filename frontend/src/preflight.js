/* Pure decision layer for the pre-flight gate.

   Deliberately kept out of Dashboard.jsx: this is the only branching logic in
   the gate, and out here it can be asserted from src/data.test.mjs with plain
   node asserts — no DOM, no renderer, no test framework to install. */

/** Most severe first. The panel headline is always findings[0]. */
export const SEVERITIES = ['block', 'warn', 'info']

const TONE = { block: 'bad', warn: 'warn', info: 'info' }

const CLEAN_HEADLINE = 'Cached inputs look consistent - nothing to flag.'

/** Unknown severities sort last rather than first (indexOf would return -1). */
const rank = sev => {
  const i = SEVERITIES.indexOf(sev)
  return i === -1 ? SEVERITIES.length : i
}

export const toneOf = sev => TONE[sev] ?? 'info'

/**
 * Decide what a Run click should do.
 *
 * `{action:'run'}` when preflight returned nothing usable — the gate must
 * never be the thing that stops a demo. Otherwise `{action:'confirm', ...}`
 * carrying everything the panel renders, headline first: the top layer states
 * the consequence in one sentence, the findings behind it carry the evidence.
 */
export function gateDecision(data) {
  if (!data || !Array.isArray(data.findings)) return { action: 'run' }

  const findings = [...data.findings].sort((a, b) => rank(a.severity) - rank(b.severity))
  const at = sev => findings.filter(f => f.severity === sev).length
  const counts = { block: at('block'), warn: at('warn'), info: at('info') }
  const top = findings[0]

  return {
    action: 'confirm',
    findings,
    counts,
    serious: counts.block + counts.warn,
    estimate: data.estimated_duration_s ?? null,
    headline: top ? top.title : CLEAN_HEADLINE,
    tone: top ? toneOf(top.severity) : 'ok',
  }
}
