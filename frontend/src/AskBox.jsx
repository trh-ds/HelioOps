import { useCallback, useEffect, useRef, useState } from 'react'
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
  const [pending, setPending] = useState(null)
  const [error, setError] = useState(null)
  const inputRef = useRef(null)
  const endRef = useRef(null)

  const busy = pending !== null

  // A chat that answers above the fold you are looking at has not answered.
  useEffect(() => {
    if (turns.length || pending) endRef.current?.scrollIntoView({ block: 'nearest' })
  }, [turns, pending])

  const send = useCallback(() => {
    const q = question.trim()
    if (!q || busy) return
    setPending(q)
    setError(null)
    setQuestion('')
    ask(industry, q, advisoryId)
      .then(res =>
        setTurns(t => [...t, { q, answer: res.answer, sources: res.sources_cited ?? [] }])
      )
      .catch(err => {
        // Put the question back in the box. A failed send that also eats what
        // you typed makes you retype it to retry.
        setQuestion(q)
        setError(
          /429/.test(err.message)
            ? 'Asking too quickly - wait a few seconds and try again.'
            : err.message
        )
      })
      .finally(() => {
        setPending(null)
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

  const body = (
    <>
      <div className="ask-log">
        {turns.length === 0 && !busy && (
          <p className="ask-empty small muted">
            The {industry} agent answers from the {industry} rulebooks it
            retrieves, and says so when the knowledge base does not cover the
            question. Every answer carries the sources it used.
          </p>
        )}

        {turns.length > 0 && (
          <ol className="ask-turns">
            {turns.map((t, i) => (
              <li key={i}>
                <div className="ask-q">{t.q}</div>
                <div className="ask-a">{t.answer}</div>
                {t.sources.length > 0 && (
                  <div className="ask-sources small muted">
                    <span className="ask-sources-label">sources</span>
                    {t.sources.map((s, j) => (
                      <span key={j} className="ask-source">
                        {Citation ? <Citation refText={s} /> : s}
                      </span>
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ol>
        )}

        {/* The pending question stays on screen while it is in flight, so the
            log never blanks out between asking and answering. */}
        {busy && (
          <ol className="ask-turns">
            <li className="is-pending">
              <div className="ask-q">{pending}</div>
              <div className="ask-a ask-typing small muted">
                reading the {industry} rulebook<span className="ask-dots" />
              </div>
            </li>
          </ol>
        )}

        <div ref={endRef} />
      </div>

      {error && <div className="small ask-error">{error}</div>}

      <div className="ask-input">
        <textarea
          ref={inputRef}
          rows={2}
          value={question}
          placeholder={advisoryId ? 'e.g. why 5 MHz and not 8?' : `Ask the ${industry} agent…`}
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={onKeyDown}
          disabled={busy}
          aria-label={`question for the ${industry} agent`}
        />
        <div className="ask-send">
          <button className="btn btn-primary" onClick={send} disabled={busy || !question.trim()}>
            {busy ? 'Asking…' : 'Ask'}
          </button>
          <span className="ask-hint small muted">Enter sends · Shift+Enter newline</span>
        </div>
      </div>
    </>
  )

  /* Collapsed inside an advisory card, where it is one section among many;
     open on the Ask panel, where it is the whole point of the page. */
  return advisoryId ? (
    <details className="askbox">
      <summary className="small muted">Ask the {industry} agent about this advisory</summary>
      {body}
    </details>
  ) : (
    <section className="askbox is-standalone">{body}</section>
  )
}
