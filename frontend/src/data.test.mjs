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
