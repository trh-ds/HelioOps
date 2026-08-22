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
