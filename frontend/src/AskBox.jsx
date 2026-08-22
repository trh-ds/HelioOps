import { useCallback, useRef, useState } from 'react'
import { ask } from './api.js'

/* Ask one industry agent about the advisory on this card.

   Scoped, not global: the card already knows the industry and the advisory, so
   the agent never has to ask "which one?" - the worst possible first question.
   A floating assistant would have to.

   History is per-card and in-memory only. Nothing here is a system of record;
   the advisory and its provenance already are. */
export default function AskBox({ industry, advisoryId, Citation }) {
  const [question, setQuestion] = useState('')
  const [turns, setTurns] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const inputRef = useRef(null)

  const send = useCallback(() => {
    const q = question.trim()
    if (!q || busy) return
    setBusy(true)
    setError(null)
    setQuestion('')
    ask(industry, q, advisoryId)
      .then(res =>
        setTurns(t => [...t, { q, answer: res.answer, sources: res.sources_cited ?? [] }])
      )
      .catch(err =>
        setError(
          /429/.test(err.message)
            ? 'Asking too quickly - wait a few seconds and try again.'
            : err.message
        )
      )
      .finally(() => {
        setBusy(false)
        inputRef.current?.focus()
      })
  }, [question, busy, industry, advisoryId])

  // Enter sends, Shift+Enter is a newline - the convention every chat input uses.
  const onKeyDown = e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <details className="askbox">
      <summary className="small muted">Ask the {industry} agent about this advisory</summary>

      {turns.length > 0 && (
        <ol className="ask-turns">
          {turns.map((t, i) => (
            <li key={i}>
              <div className="ask-q">{t.q}</div>
              <div className="ask-a">{t.answer}</div>
              {t.sources.length > 0 && (
                <div className="ask-sources small muted">
                  {t.sources.map((s, j) => (
                    <span key={j}>
                      {j > 0 && ' · '}
                      {Citation ? <Citation refText={s} /> : s}
                    </span>
                  ))}
                </div>
              )}
            </li>
          ))}
        </ol>
      )}

      <div className="ask-input">
        <textarea
          ref={inputRef}
          rows={2}
          value={question}
          placeholder={`e.g. why 5 MHz and not 8?`}
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={onKeyDown}
          disabled={busy}
        />
        <button className="btn" onClick={send} disabled={busy || !question.trim()}>
          {busy ? 'Asking…' : 'Ask'}
        </button>
      </div>

      {busy && <div className="small muted">The {industry} agent is reading the rulebook…</div>}
      {error && <div className="small ask-error">{error}</div>}
    </details>
  )
}
