/* Backend client.
   Paths are relative by default so vite's dev proxy (vite.config.js) forwards
   them to the API on :8000, and a single-origin deployment (one container
   serving both) needs no configuration.

   Split deployments — the SPA on Vercel, the API on a Space — have no backend
   at the SPA's origin: vercel.json rewrites /(.*) to /index.html, so
   `fetch('/api/storms')` returns the HTML shell with a 200 and every call dies
   in res.json(). Set VITE_API_URL to the API origin at BUILD time (vite inlines
   import.meta.env; a runtime env var does nothing) and the backend's CORS
   origins must list the SPA origin. */

import { citationPath } from './citation.js'

const BASE = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')

const json = async (path, init) => {
  const res = await fetch(BASE + path, init)
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail ?? detail
    } catch {
      /* non-JSON error body */
    }
    throw new Error(`${res.status} ${detail}`)
  }
  return res.json()
}

/* /health/ready answers 503 with the same body shape when degraded — parse
   unconditionally so the per-check pills render instead of "unreachable". */
export const getHealth = async () => (await fetch(BASE + '/health/ready')).json()

/* Absolute URL for a citation, or null if the ref names no document.
   The parsing lives in citation.js so the node test runner can reach it
   without vite's import.meta.env. */
export const citationUrl = ref => {
  const path = citationPath(ref)
  return path ? BASE + path : null
}

export const getStorms = () => json('/api/storms')
export const getPreflight = stormId => json(`/api/preflight/${encodeURIComponent(stormId)}`)
export const getResult = stormId => json(`/api/result/${encodeURIComponent(stormId)}`)
export const getAdvisory = id => json(`/api/advisory/${encodeURIComponent(id)}`)

export const runPipeline = stormId =>
  json(`/api/detect/${encodeURIComponent(stormId)}`, { method: 'POST' })

/** Live run over the WebSocket. Returns a close() handle.
    The backend streams pipeline.stage, agent.thinking, advisory.generated and
    pipeline.complete; `onEvent` sees every one of them in order. */
export function streamPipeline(stormId, { onEvent, onError, onClose } = {}) {
  const origin = BASE || window.location.origin
  const ws = new WebSocket(`${origin.replace(/^http/, 'ws')}/ws/stream`)

  ws.onopen = () => ws.send(JSON.stringify({ action: 'run_pipeline', storm_id: stormId }))
  ws.onmessage = e => {
    let msg
    try {
      msg = JSON.parse(e.data)
    } catch {
      return
    }
    onEvent?.(msg)
    // pipeline.complete is the last event of a run; the socket itself stays
    // open so a second run can reuse it, but the UI can stop waiting here.
    if (msg.event === 'pipeline.complete') onClose?.(msg)
  }
  ws.onerror = () => onError?.(new Error('WebSocket error — is the backend reachable?'))
  ws.onclose = () => onClose?.()

  return () => ws.readyState <= 1 && ws.close()
}
