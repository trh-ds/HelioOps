"""
Regression tests for the GenAI LLM layer's rate limiting and model config.

These cover the three failures that took the agentic layer down in production:

  1. Configured models were decommissioned by Groq and 404'd, so every advisory
     fell through to the ESCALATE_TO_SPECIALIST fallback.
  2. Four agents fired ~26k tokens into an 8k/min window with no 429 handling,
     which burned all retry attempts in under a second.
  3. gpt-oss reasoning tokens are billed against max_tokens, so without
     reasoning_effort="low" the JSON came back truncated.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from backend.genai import config as genai_config
from backend.genai.llm import (
    _TokenBucket,
    _estimate_tokens,
    _parse_duration,
    _supports_reasoning_effort,
    reset_buckets,
)


# ── Model configuration ──────────────────────────────────────────────────────

# Groq removed these. Anything still pointing at them is a 404 at runtime.
DECOMMISSIONED = {
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "llama3-70b-8192",
    "llama3-8b-8192",
    "mixtral-8x7b-32768",
    "gemma-7b-it",
}


def test_advisory_model_is_not_decommissioned():
    assert genai_config.GROQ_MODEL not in DECOMMISSIONED


def test_checker_model_is_not_decommissioned():
    assert genai_config.GROQ_CHECKER_MODEL not in DECOMMISSIONED


def test_checker_uses_a_different_model_than_the_advisory():
    """Groq meters TPM per model, so a distinct checker model is a distinct budget."""
    assert genai_config.GROQ_CHECKER_MODEL != genai_config.GROQ_MODEL


def test_reasoning_effort_is_low_for_reasoning_models():
    """
    gpt-oss returns chain-of-thought in a separate field but bills it against
    max_tokens. At default effort a full advisory prompt returns
    finish_reason="length" and truncated JSON.
    """
    if _supports_reasoning_effort(genai_config.GROQ_MODEL):
        assert genai_config.GROQ_REASONING_EFFORT == "low"


def test_reasoning_effort_only_sent_to_models_that_accept_it():
    assert _supports_reasoning_effort("openai/gpt-oss-120b")
    assert _supports_reasoning_effort("openai/gpt-oss-20b")
    # Sending reasoning_effort to a non-reasoning model is a 400.
    assert not _supports_reasoning_effort("llama-3.3-70b-versatile")
    assert not _supports_reasoning_effort("allam-2-7b")


def test_context_budget_leaves_room_for_fixed_prompt_overhead():
    """MAX_CONTEXT_TOKENS budgets chunks only; the rest of the prompt is on top."""
    assert genai_config.MAX_CONTEXT_TOKENS < genai_config.MAX_PROMPT_TOKENS
    assert (
        genai_config.MAX_PROMPT_TOKENS - genai_config.MAX_CONTEXT_TOKENS
        >= genai_config.PROMPT_FIXED_OVERHEAD_TOKENS
    )


def test_self_check_is_non_blocking_by_default():
    """
    A flagged advisory used to trigger a full regeneration. That tripled token
    spend on the anchor storms and reproduced the same flagged numerics.
    """
    assert genai_config.SELF_CHECK_BLOCKING is False


# ── Token bucket ─────────────────────────────────────────────────────────────


def test_bucket_admits_up_to_the_limit_without_waiting():
    async def run():
        bucket = _TokenBucket(1000)
        start = time.monotonic()
        for _ in range(4):
            await bucket.acquire(250)
        return time.monotonic() - start

    assert asyncio.run(run()) < 0.5


def test_bucket_blocks_once_the_window_is_full():
    """The 5th request must not be admitted while the window holds 1000/1000."""

    async def run():
        bucket = _TokenBucket(1000)
        for _ in range(4):
            await bucket.acquire(250)
        try:
            await asyncio.wait_for(bucket.acquire(250), timeout=0.4)
            return "admitted"
        except asyncio.TimeoutError:
            return "blocked"

    assert asyncio.run(run()) == "blocked"


def test_reconcile_frees_the_unused_part_of_a_reservation():
    """
    Reservations assume worst-case completion. Once real usage comes back the
    surplus has to become available again, or the bucket throttles on tokens
    that were never spent.
    """

    async def run():
        bucket = _TokenBucket(1000)
        res = await bucket.acquire(900)
        assert bucket._in_window() == 900
        await bucket.reconcile(res, 200)
        assert bucket._in_window() == 200
        # Freed capacity is immediately reusable.
        await asyncio.wait_for(bucket.acquire(700), timeout=0.4)

    asyncio.run(run())


def test_release_drops_a_reservation_for_a_call_that_never_landed():
    async def run():
        bucket = _TokenBucket(1000)
        res = await bucket.acquire(1000)
        await bucket.release(res)
        assert bucket._in_window() == 0
        await asyncio.wait_for(bucket.acquire(1000), timeout=0.4)

    asyncio.run(run())


def test_reconcile_does_not_outlive_its_reservation():
    """
    An earlier design offset a reservation with a compensating negative entry.
    The correction carried a later timestamp, so it outlived the reservation it
    cancelled and left the window under-counted — letting real usage exceed the
    limit at window edges. Corrections must mutate the original entry instead.
    """

    async def run():
        bucket = _TokenBucket(1000)
        res = await bucket.acquire(800)
        await bucket.reconcile(res, 100)
        assert bucket._in_window() >= 0
        assert len(bucket._events) == 1

    asyncio.run(run())


def test_request_larger_than_the_whole_limit_does_not_deadlock():
    async def run():
        bucket = _TokenBucket(1000)
        await asyncio.wait_for(bucket.acquire(50_000), timeout=0.5)

    asyncio.run(run())


def test_concurrent_agents_never_exceed_the_window():
    """The scenario that broke production: parallel fan-out into one TPM budget."""

    async def run():
        bucket = _TokenBucket(8000)
        peak = 0

        async def agent():
            nonlocal peak
            res = await bucket.acquire(3000)
            peak = max(peak, bucket._in_window())
            await asyncio.sleep(0.05)
            await bucket.reconcile(res, 3000)

        await asyncio.wait_for(asyncio.gather(*(agent() for _ in range(2))), timeout=2)
        return peak

    assert asyncio.run(run()) <= 8000


def test_key_pool_multiplies_capacity():
    """
    Groq meters TPM per (key, model), so N keys is N independent budgets.
    With one key an 8000-token budget admits two 4000-token calls; with two
    keys it admits four, without any of them waiting.
    """
    from backend.genai import llm

    async def run(keys):
        llm.reset_buckets()
        original = llm.GROQ_API_KEYS
        llm.GROQ_API_KEYS = keys
        try:
            admitted = 0
            for _ in range(4):
                try:
                    await asyncio.wait_for(llm._acquire_slot("m", 4000), timeout=0.3)
                    admitted += 1
                except asyncio.TimeoutError:
                    break
            return admitted
        finally:
            llm.GROQ_API_KEYS = original
            llm.reset_buckets()

    assert asyncio.run(run(["k1"])) == 2
    assert asyncio.run(run(["k1", "k2"])) == 4


def test_penalised_key_is_taken_out_of_rotation():
    """
    On a 429 the server's accounting wins. Simply releasing the reservation
    made the bucket look emptier, so the router handed the same exhausted key
    straight back and the retry loop burned its attempts on one key while the
    rest of the pool sat idle.
    """
    from backend.genai import llm

    async def run():
        llm.reset_buckets()
        original = llm.GROQ_API_KEYS
        llm.GROQ_API_KEYS = ["k1", "k2"]
        try:
            await llm._bucket_for("m", "k1").penalise(30.0)
            # k1 is parked, so every acquire must land on k2.
            keys = [(await llm._acquire_slot("m", 500))[0] for _ in range(3)]
            return keys
        finally:
            llm.GROQ_API_KEYS = original
            llm.reset_buckets()

    assert asyncio.run(run()) == ["k2", "k2", "k2"]


def test_penalty_expires():
    async def run():
        bucket = _TokenBucket(1000)
        await bucket.penalise(0.2)
        assert await bucket.try_acquire(500) is None
        await asyncio.sleep(0.35)
        assert await bucket.try_acquire(500) is not None

    asyncio.run(run())


def test_key_pool_spreads_load_instead_of_pinning_one_key():
    from backend.genai import llm

    async def run():
        llm.reset_buckets()
        original = llm.GROQ_API_KEYS
        llm.GROQ_API_KEYS = ["k1", "k2"]
        try:
            used = [(await llm._acquire_slot("m", 1000))[0] for _ in range(4)]
            return used
        finally:
            llm.GROQ_API_KEYS = original
            llm.reset_buckets()

    used = asyncio.run(run())
    assert set(used) == {"k1", "k2"}, f"load did not spread: {used}"
    assert used.count("k1") == used.count("k2") == 2


def test_single_key_pool_behaves_exactly_like_one_bucket():
    from backend.genai import llm

    async def run():
        llm.reset_buckets()
        original = llm.GROQ_API_KEYS
        llm.GROQ_API_KEYS = ["only"]
        try:
            key, _ = await llm._acquire_slot("m", 100)
            assert key == "only"
            assert await llm._bucket_for("m", "only").headroom() == GROQ_TPM_LIMIT_FALLBACK - 100
        finally:
            llm.GROQ_API_KEYS = original
            llm.reset_buckets()

    asyncio.run(run())


GROQ_TPM_LIMIT_FALLBACK = genai_config.GROQ_TPM_LIMIT


def test_same_key_different_models_are_separate_budgets():
    from backend.genai.llm import _bucket_for

    reset_buckets()
    assert _bucket_for("openai/gpt-oss-120b", "k1") is not _bucket_for("openai/gpt-oss-20b", "k1")
    reset_buckets()


def test_buckets_are_isolated_per_model():
    """
    Verified against the live API: burning tokens on gpt-oss-120b left
    gpt-oss-20b's remaining-token counter untouched. Putting the self-check on
    a different model therefore buys a whole separate budget.
    """
    from backend.genai.llm import _bucket_for

    reset_buckets()
    a = _bucket_for("openai/gpt-oss-120b")
    b = _bucket_for("openai/gpt-oss-20b")
    assert a is not b
    assert _bucket_for("openai/gpt-oss-120b") is a
    reset_buckets()


# ── Retry-After parsing ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("12", 12.0),
        ("4.995s", 4.995),
        ("630ms", 0.63),
        ("1m26.4s", 86.4),
        ("2m", 120.0),
    ],
)
def test_parse_groq_duration_formats(raw, expected):
    """Groq returns reset hints as Go durations, not plain seconds."""
    assert _parse_duration(raw) == pytest.approx(expected, rel=1e-3)


def test_parse_duration_rejects_garbage():
    assert _parse_duration("soon") is None


def test_low_coverage_ignores_generic_impact_matrix_chunks():
    """
    Every industry is handed 2 impact_matrix chunks regardless of how well its
    own KB covers the query. Counting those toward coverage made the flag
    unreachable for any KB holding 1+ chunk — which is how maritime shipped
    clean off a 2-page publisher catalogue page.
    """
    from backend.genai.guardrails import apply_safety_flags
    from backend.genai.models import (
        ActionItem,
        AdvisoryOutput,
        Industry,
        SafetyFlag,
        SeverityTier,
    )
    from datetime import datetime, timezone

    def chunk(source):
        from backend.genai.models import RetrievedChunk

        return RetrievedChunk(
            chunk_id=f"c{source}", text="x", source=source, similarity=0.8, metadata={}
        )

    def advisory():
        return AdvisoryOutput(
            advisory_id="a",
            storm_event_id="s",
            industry=Industry("maritime"),
            severity=SeverityTier("HIGH"),
            confidence_score=0.9,
            summary="Storm summary for the test fixture.",
            action_items=[
                ActionItem(step=1, action="Monitor HF distress frequencies",
                           rationale="Storm degrades GMDSS comms", source_ref="imo.pdf",
                           time_window="T+0")
            ],
            estimated_impact_window=None,
            sources_cited=["imo.pdf"],
            validation_passed=True,
            generated_at=datetime.now(timezone.utc),
            model_used="m",
            safety_flags=[],
            generation_errors=[],
        )

    industry_chunks = [chunk("imo.pdf"), chunk("imo.pdf")]
    impact_chunks = [chunk("noaa.txt"), chunk("noaa.txt")]
    combined = industry_chunks + impact_chunks

    # 4 combined chunks clears the threshold of 3 — the old, wrong reading.
    lenient = apply_safety_flags(advisory(), combined, 0.8)
    assert SafetyFlag.LOW_COVERAGE not in lenient.safety_flags

    # 2 industry chunks does not.
    strict = apply_safety_flags(
        advisory(), combined, 0.8, industry_chunk_count=len(industry_chunks)
    )
    assert SafetyFlag.LOW_COVERAGE in strict.safety_flags


def test_well_covered_industry_is_not_flagged():
    from backend.genai.guardrails import apply_safety_flags
    from backend.genai.models import (
        ActionItem,
        AdvisoryOutput,
        Industry,
        RetrievedChunk,
        SafetyFlag,
        SeverityTier,
    )
    from datetime import datetime, timezone

    chunks = [
        RetrievedChunk(chunk_id=f"c{i}", text="x", source="nat_doc_007_2025.pdf",
                       similarity=0.8, metadata={})
        for i in range(5)
    ]
    adv = AdvisoryOutput(
        advisory_id="a", storm_event_id="s", industry=Industry("aviation"),
        severity=SeverityTier("HIGH"), confidence_score=0.9, summary="Storm summary for the test fixture.",
        action_items=[ActionItem(step=1, action="Switch to alternate HF band",
                                 rationale="Polar HF propagation is degraded",
                                 source_ref="nat_doc_007_2025.pdf", time_window="T+0")],
        estimated_impact_window=None, sources_cited=["nat_doc_007_2025.pdf"],
        validation_passed=True, generated_at=datetime.now(timezone.utc),
        model_used="m", safety_flags=[], generation_errors=[],
    )
    out = apply_safety_flags(adv, chunks, 0.8, industry_chunk_count=5)
    assert SafetyFlag.LOW_COVERAGE not in out.safety_flags


# ── Citation matching ────────────────────────────────────────────────────────

REAL_SOURCES = [
    "itu_r_m541_dsc_operational_procedures.pdf",
    "itu_r_p618_earth_space_propagation.pdf",
    "nerc_tpl007_4.pdf",
    "nat_doc_007_2025.pdf",
    "noaa_space_weather_scales.txt",
]


def _grounded(ref: str) -> bool:
    from backend.genai.guardrails import citation_matches

    return any(citation_matches(ref, s) for s in REAL_SOURCES)


@pytest.mark.parametrize(
    "ref",
    [
        "ITU-R M.541",           # designator, punctuated
        "ITU-R M.541-11",        # designator with version suffix
        "ITU-R P.618",
        "NERC TPL-007-4",        # separated letter/digit runs
        "ICAO NAT Doc 007",
        "NOAA Space Weather Scales",   # no designator, word overlap
        "itu_r_m541_dsc_operational_procedures.pdf",  # verbatim filename
    ],
)
def test_natural_citations_resolve_to_their_source(ref):
    """
    Matching was `ref in src or src in ref`, so only a verbatim filename ever
    matched. Models cite the way people do, so real citations were scored as
    CITATION_GAP and docked confidence for being correct.
    """
    assert _grounded(ref), f"{ref!r} should resolve to a real source"


@pytest.mark.parametrize(
    "ref",
    [
        "NERC TPL-999-9",        # right family, wrong standard
        "ICAO Annex 2",          # plausible, not retrieved
        "SOURCE UNAVAILABLE — consult space weather specialist",
        "made up standard",
        "",
    ],
)
def test_ungrounded_citations_are_rejected(ref):
    assert not _grounded(ref), f"{ref!r} must not resolve to a source"


def test_citation_grounding_accepts_a_chunk_id():
    from backend.genai.guardrails import citation_is_grounded
    from backend.genai.models import RetrievedChunk

    chunk = RetrievedChunk(
        chunk_id="abc123", text="x", source="itu_r_m541_dsc_operational_procedures.pdf",
        similarity=0.8, metadata={},
    )
    assert citation_is_grounded("abc123", [chunk])
    assert citation_is_grounded("ITU-R M.541", [chunk])
    assert not citation_is_grounded("NERC TPL-007-4", [chunk])


def _chunks(n, chars):
    from backend.genai.models import RetrievedChunk

    return [
        RetrievedChunk(
            chunk_id=f"c{i}", text="x" * chars, source=f"src{i}.pdf",
            similarity=0.9 - i * 0.01, metadata={},
        )
        for i in range(n)
    ]


def test_self_check_sees_every_chunk_the_generator_saw():
    """
    The auditor was handed the top-N chunks truncated to MAX_CONTEXT_TOKENS*2
    chars with a `break` on the first oversized chunk — measured at 1 of 5
    chunks, 35% of the generator's context. Auditing a third of the evidence
    flags grounded claims, so HALLUCINATION_DETECTED fired on nearly every
    advisory and the flag carried no information.
    """
    from backend.genai.guardrails import build_self_check_context

    # A realistic generator payload: RAG_TOP_K industry chunks + 2 impact ones,
    # sized like the real corpus (~500 tokens ≈ 2000 chars each).
    chunks = _chunks(genai_config.RAG_TOP_K + 2, 1400)
    _, included = build_self_check_context(chunks)
    assert included == len(chunks), (
        f"auditor sees {included}/{len(chunks)} chunks — it must see all of them"
    )


def test_self_check_skips_an_oversized_chunk_without_dropping_the_rest():
    """`break` on the first chunk that does not fit discarded everything after it."""
    from backend.genai.guardrails import build_self_check_context

    budget_chars = genai_config.MAX_CONTEXT_TOKENS * 4
    oversized = _chunks(1, budget_chars + 500)
    small = _chunks(3, 200)
    for c, sim in zip(oversized + small, [0.99, 0.5, 0.4, 0.3]):
        c.similarity = sim
    _, included = build_self_check_context(oversized + small)
    assert included == 3, f"expected the 3 small chunks to survive, got {included}"


def test_token_estimate_is_in_the_right_ballpark():
    text = "space weather advisory " * 50
    assert 100 < _estimate_tokens(text) < 400
