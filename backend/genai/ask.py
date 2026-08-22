"""
backend/genai/ask.py — per-agent operator chatbot.

Scoped to ONE industry and (optionally) ONE advisory, so the agent never has to
ask "which domain?" as its first question. Everything here composes pieces that
already exist: retrieve_chunks for grounding, the repository for the advisory
under discussion, complete_json for the call.

Two deliberate choices:

* It runs on GROQ_CHECKER_MODEL (gpt-oss-20b), not GROQ_MODEL. Groq meters TPM
  per (key, model), so chat draws on a DIFFERENT bucket and can never starve an
  advisory run of the budget it needs. That is the entire reason not to reuse
  the advisory model here.
* A failure returns a plain answer instead of raising. Chat is a convenience on
  top of the console; a dead LLM must degrade to "I could not answer that",
  never to a 500 that makes the card look broken.
"""

from __future__ import annotations

import json
import logging

from backend.genai.config import (
    GROQ_CHECKER_MAX_TOKENS,
    GROQ_CHECKER_MODEL,
    INDUSTRY_KB_MAP,
    RAG_TOP_K,
)
from backend.genai.guardrails import _extract_json
from backend.genai.llm import complete_json
from backend.genai.prompts.ask import (
    ADVISORY_BLOCK_TEMPLATE,
    ASK_SYSTEM_PROMPT,
    ASK_USER_TEMPLATE,
)
from backend.genai.retriever import format_context, retrieve_chunks

log = logging.getLogger(__name__)

MAX_QUESTION_CHARS = 500
_UNAVAILABLE = (
    "I could not reach the advisory model just now. The advisory itself is "
    "unaffected - retry in a moment, or consult a space weather specialist."
)


def _advisory_block(advisory: dict | None, industry: str) -> str:
    """Render the advisory under discussion, or nothing if there is not one."""
    if not advisory:
        return ""
    inner = advisory.get("advisory") if isinstance(advisory, dict) else None
    adv = inner if isinstance(inner, dict) else advisory

    actions = adv.get("action_items") or []
    rendered = "\n".join(
        f"  {a.get('step', i + 1)}. {a.get('action', '')}"
        f"  [source: {a.get('source_ref', 'none')}]"
        for i, a in enumerate(actions)
    ) or "  (none)"

    return ADVISORY_BLOCK_TEMPLATE.format(
        industry=industry,
        severity=adv.get("severity", "unknown"),
        summary=adv.get("summary", "(no summary)"),
        actions=rendered,
    )


async def answer_question(
    industry: str,
    question: str,
    advisory: dict | None = None,
) -> dict:
    """
    Answer one operator question against one industry knowledge base.

    Returns {"answer": str, "sources_cited": list[str]}. Raises ValueError for
    an unknown industry or an empty question - those are caller bugs and the
    route turns them into a 400. Everything else degrades to a stated
    non-answer rather than propagating.
    """
    kb = INDUSTRY_KB_MAP.get(industry)
    if kb is None:
        raise ValueError(
            f"Unknown industry '{industry}'. Expected one of {sorted(INDUSTRY_KB_MAP)}."
        )

    question = (question or "").strip()
    if not question:
        raise ValueError("Question must not be empty.")
    question = question[:MAX_QUESTION_CHARS]

    chunks = retrieve_chunks(kb, question, top_k=RAG_TOP_K)
    context = format_context(chunks)

    system = ASK_SYSTEM_PROMPT.format(industry=industry)
    user = ASK_USER_TEMPLATE.format(
        question=question,
        advisory_block=_advisory_block(advisory, industry),
        context=context,
    )

    try:
        raw = await complete_json(
            system,
            user,
            model=GROQ_CHECKER_MODEL,
            max_tokens=GROQ_CHECKER_MAX_TOKENS,
        )
        parsed = json.loads(_extract_json(raw))
    except Exception as exc:
        log.warning("ask failed for industry=%s: %s", industry, exc)
        return {"answer": _UNAVAILABLE, "sources_cited": []}

    answer = str(parsed.get("answer") or "").strip() or _UNAVAILABLE
    sources = parsed.get("sources_cited") or []
    if not isinstance(sources, list):
        sources = [str(sources)]

    return {
        "answer": answer,
        # Only surface citations the retrieval actually returned - the same
        # posture as the advisory path, so a chat answer cannot invent a source
        # the operator would then try to open.
        "sources_cited": [
            s for s in (str(x).strip() for x in sources)
            if s and any(c.source in s or s in c.source for c in chunks)
        ],
    }
