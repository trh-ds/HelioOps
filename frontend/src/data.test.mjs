import assert from 'node:assert/strict'
import { INDUSTRIES, KP, wrap } from './data.js'

// wrap() is the only branching logic on the page — check both edges.
assert.equal(wrap(0, -1), INDUSTRIES.length - 1, 'left from first wraps to last')
assert.equal(wrap(INDUSTRIES.length - 1, 1), 0, 'right from last wraps to first')
assert.equal(wrap(1, 1), 2)

// every G level the storm HUD can select must have a Kp label
for (let g = 1; g <= 5; g++) assert.ok(KP[g], `missing Kp for G${g}`)

// the globe only knows these four accents; a typo'd key silently falls back
assert.deepEqual(
  INDUSTRIES.map(i => i.key),
  ['aviation', 'grid', 'maritime', 'telecom']
)

console.log('ok — data.test.mjs')

/* ---------- pre-flight gate decision ---------- */
const { gateDecision } = await import('./preflight.js')

// The gate must never be the thing that breaks a run. Anything unusable from
// the endpoint means: skip the panel, start the pipeline.
assert.equal(gateDecision(null).action, 'run', 'null response runs directly')
assert.equal(gateDecision(undefined).action, 'run', 'thrown/absent response runs directly')
assert.equal(gateDecision({}).action, 'run', 'response with no findings array runs directly')

// Headline is the most severe finding, whatever order the API sent them in.
const mixed = gateDecision({
  estimated_duration_s: 72,
  findings: [
    { id: 'c', severity: 'info', title: 'info one', detail: 'd' },
    { id: 'a', severity: 'block', title: 'rate limited', detail: 'd' },
    { id: 'b', severity: 'warn', title: 'stale cache', detail: 'd' }
  ]
})
assert.equal(mixed.action, 'confirm')
assert.equal(mixed.headline, 'rate limited', 'block outranks warn and info')
assert.equal(mixed.tone, 'bad')
assert.equal(mixed.serious, 2, 'block + warn are the ones worth reviewing')
assert.deepEqual(mixed.counts, { block: 1, warn: 1, info: 1 })
assert.deepEqual(mixed.findings.map(f => f.id), ['a', 'b', 'c'], 'sorted most severe first')
assert.equal(mixed.estimate, 72)

// A clean preflight still confirms, but says so in words rather than a blank.
const clean = gateDecision({ estimated_duration_s: 70, findings: [] })
assert.equal(clean.action, 'confirm')
assert.equal(clean.tone, 'ok')
assert.equal(clean.serious, 0)
assert.match(clean.headline, /consistent/, 'clean run gets a real sentence')

// An unrecognised severity must not sort to the front and hijack the headline.
const odd = gateDecision({
  findings: [
    { id: 'x', severity: 'nonsense', title: 'unknown', detail: 'd' },
    { id: 'y', severity: 'warn', title: 'real warning', detail: 'd' }
  ]
})
assert.equal(odd.headline, 'real warning', 'unknown severity sorts last')

console.log('ok — preflight gate decision')

/* ---- citationUrl: page-accurate deep links ---- */
{
  const { citationPath } = await import('./citation.js')
  const citationUrl = citationPath
  const q = s => decodeURIComponent(s)

  assert.equal(citationUrl(null), null, 'no ref -> no link')
  assert.equal(citationUrl('ICAO NAT Doc 007'), null, 'ref naming no file -> no link')

  const withPage = citationUrl('nat_doc_007_2025.pdf p.42')
  assert.ok(q(withPage).endsWith('/api/kb/source/nat_doc_007_2025.pdf#page=42'), withPage)

  const spaced = citationUrl('nat_doc_007_2025.pdf p. 7')
  assert.ok(q(spaced).endsWith('#page=7'), spaced)

  const worded = citationUrl('nerc_tpl007_4.pdf page 12')
  assert.ok(q(worded).endsWith('#page=12'), worded)

  // Missing page still links the document - page 1 beats a dead link.
  const noPage = citationUrl('noaa_space_weather_scales.txt')
  assert.ok(q(noPage).endsWith('/api/kb/source/noaa_space_weather_scales.txt'), noPage)
  assert.ok(!noPage.includes('#page='), 'no page fragment when none was cited')

  console.log('ok — citationUrl')
}

/* ---------- console panels: provenance chain + interval bars ---------- */
{
  const { chainSteps, intervalGeometry, elapsed, PROVENANCE_STEPS } = await import('./console.js')

  // A complete trace is 6 of 6, in canonical order regardless of arrival order.
  const full = chainSteps({
    chain: [...PROVENANCE_STEPS].reverse().map(step => ({ step, ref: `${step}-ref` }))
  })
  assert.equal(full.present, 6)
  assert.equal(full.total, 6)
  assert.deepEqual(full.steps.map(s => s.step), PROVENANCE_STEPS, 'canonical order, not arrival order')

  // A gap is rendered as a gap. Silently dropping it makes 5 steps look like 6.
  const gapped = chainSteps({ chain: [{ step: 'detection', ref: 'd' }, { step: 'output', ref: 'o' }] })
  assert.equal(gapped.present, 2)
  assert.equal(gapped.steps.length, 6, 'missing steps still occupy their slot')
  assert.equal(gapped.steps.find(s => s.step === 'raw_data').present, false)

  // Nothing usable must not throw — the panel has an empty state for this.
  assert.equal(chainSteps(null).present, 0)
  assert.equal(chainSteps({}).steps.length, 6)

  // A 7th step must be visible the day it ships, not silently discarded.
  const extra = chainSteps({ chain: [{ step: 'notification', ref: 'n' }] })
  assert.equal(extra.steps.length, 7)
  assert.equal(extra.present, 0, 'an extra step is not a canonical step')

  // Interval geometry: median sits inside the band, band sits inside the domain.
  const g = intervalGeometry(6.8, 12.8, 13.7)
  assert.ok(g.leftPct > 0 && g.leftPct + g.widthPct < 100, 'padded domain, bar never touches the edge')
  assert.ok(g.medPct > g.leftPct && g.medPct < g.leftPct + g.widthPct, 'median inside the band')

  // Quantile crossing must not invert the bar.
  const crossed = intervalGeometry(13.7, 12.8, 6.8)
  assert.deepEqual([crossed.lo, crossed.med, crossed.hi], [6.8, 12.8, 13.7], 'sorted, not trusted')
  assert.ok(crossed.widthPct > 0)

  // A fixed domain (probability) is honoured rather than padded past its bounds.
  const prob = intervalGeometry(0, 0.5, 1, { min: 0, max: 1 })
  assert.equal(prob.leftPct, 0)
  assert.equal(prob.widthPct, 100)
  assert.equal(prob.medPct, 50)

  // Degenerate and unusable inputs.
  assert.ok(intervalGeometry(5, 5, 5).widthPct === 0, 'zero span still has a domain')
  assert.equal(intervalGeometry(1, 2, null), null, 'no bar without three numbers')
  assert.equal(intervalGeometry(1, 2, 'x'), null)

  // Stream clock.
  assert.equal(elapsed(1000, 1000), '0:00')
  assert.equal(elapsed(0, 72_000), '1:12')
  assert.equal(elapsed(5000, 1000), '0:00', 'never renders a negative clock')
  assert.equal(elapsed(null, 1000), '')

  console.log('ok — console panels')
}
