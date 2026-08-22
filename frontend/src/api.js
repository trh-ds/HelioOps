/* Backend client.
   Paths are relative so vite's dev proxy (vite.config.js) forwards them to the
   API on :8000; in a built deployment they hit whatever origin serves the app. */

const json = async (path, init) => {
  const res = await fetch(path, init)
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

export const getHealth = () => json('/health/ready')
export const getStorms = () => json('/api/storms')
export const getResult = stormId => json(`/api/result/${encodeURIComponent(stormId)}`)
export const getAdvisory = id => json(`/api/advisory/${encodeURIComponent(id)}`)

export const runPipeline = stormId =>
  json(`/api/detect/${encodeURIComponent(stormId)}`, { method: 'POST' })

/** Live run over the WebSocket. Returns a close() handle.
    The backend streams pipeline.stage, agent.thinking, advisory.generated and
    pipeline.complete; `onEvent` sees every one of them in order. */
export function streamPipeline(stormId, { onEvent, onError, onClose } = {}) {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const ws = new WebSocket(`${proto}://${window.location.host}/ws/stream`)

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
  ws.onerror = () => onError?.(new Error('WebSocket error — is the backend running on :8000?'))
  ws.onclose = () => onClose?.()

  return () => ws.readyState <= 1 && ws.close()
}
