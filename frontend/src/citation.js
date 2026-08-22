/* Pure citation parsing.

   Kept out of api.js for the same reason preflight.js exists: api.js reads
   `import.meta.env`, which only vite defines, so importing it from the plain
   node test runner throws. Nothing here touches the environment, so
   src/data.test.mjs can assert it directly - no vitest, no jsdom. */

/** Files the console can open. Anything else is not a link. */
const SOURCE_FILE = /[\w.-]+\.(?:pdf|txt|md)\b/i

/** "p.42", "p. 42", "pp.10-12", "page 7" - all name a page. */
const PAGE = /\bp{1,2}\.?\s*(\d+)|\bpages?\s+(\d+)/i

/**
 * Path + fragment for a citation, or null when the ref names no document.
 *
 * source_ref arrives as "nat_doc_007_2025.pdf p.42" now that retrieved chunks
 * advertise their page. Chrome's and Firefox's built-in PDF viewers honour
 * `#page=N` natively, so a plain anchor is the whole feature - no PDF.js.
 *
 * A ref that is only a regulation code ("ICAO NAT Doc 007") returns null, so
 * the caller renders plain text rather than a link that 404s.
 */
export function citationPath(ref) {
  if (!ref) return null
  const file = String(ref).match(SOURCE_FILE)
  if (!file) return null

  const page = String(ref).match(PAGE)
  const n = page ? (page[1] ?? page[2]) : null

  // No page cited -> still link the document. Page 1 beats a dead link.
  return `/api/kb/source/${encodeURIComponent(file[0])}${n ? `#page=${n}` : ''}`
}
