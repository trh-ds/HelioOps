"""
The one place HelioOps talks to Groq.

Replaces langchain-core + langchain-groq, which were pulling a large dependency
tree to build two dicts and read `.choices[0].message.content`.

Beyond the plain call, this module owns the two things that were missing and
that made the GenAI layer fail under load:

  1. A client-side TPM bucket, per model. Groq meters tokens-per-minute per
     model, so each model gets its own window here. Calls wait for room instead
     of firing into a 429.
  2. Retry on the 429s that still get through (the bucket is an estimate — the
     server counts the real thing), honouring Retry-After.

Both were absent before: a rate limit surfaced as a bare exception inside the
agent's generation loop, which counted it as a failed attempt and retried
immediately, burning all three attempts in under a second and emitting a
fallback advisory.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time


from groq import AsyncGroq, RateLimitError

from backend.genai.config import (
    GROQ_API_KEYS,
    GROQ_MAX_RETRIES,
    GROQ_MAX_TOKENS,
    GROQ_MODEL,
    GROQ_REASONING_EFFORT,
    GROQ_REQUEST_TIMEOUT_S,
    GROQ_TEMPERATURE,
    GROQ_TPM_LIMIT,
)

log = logging.getLogger(__name__)


class TruncatedCompletion(RuntimeError):
    """The model stopped at max_tokens, so the JSON is incomplete."""


_clients: dict[str, AsyncGroq] = {}

# Models that accept the `reasoning_effort` parameter. Sending it to a
# non-reasoning model is a 400, so it is opt-in by prefix.
_REASONING_MODEL_PREFIXES = ("openai/gpt-oss", "qwen/qwen3")

_WINDOW_SECONDS = 60.0


def _get_client(api_key: str) -> AsyncGroq:
    if api_key not in _clients:
        _clients[api_key] = AsyncGroq(api_key=api_key)
    return _clients[api_key]


def _supports_reasoning_effort(model: str) -> bool:
    return model.startswith(_REASONING_MODEL_PREFIXES)


# ── Token estimation ─────────────────────────────────────────────────────────

_enc = None


def _estimate_tokens(text: str) -> int:
    """Approximate token count for pre-flight budgeting."""
    global _enc
    if _enc is None:
        try:
            import tiktoken

            _enc = tiktoken.get_encoding("cl100k_base")
        except Exception:  # pragma: no cover - tiktoken is a hard dep in practice
            _enc = False
    if _enc:
        return len(_enc.encode(text))
    # cl100k averages ~4 chars/token on English prose.
    return len(text) // 4


# ── Per-model sliding-window TPM bucket ──────────────────────────────────────


class _TokenBucket:
    """
    Sliding 60-second token window for one model.

    Groq's limit is a rolling TPM, not a fixed calendar minute, so this keeps
    (timestamp, tokens) pairs and evicts anything older than the window rather
    than resetting on a tick.
    """

    def __init__(self, limit_per_minute: int) -> None:
        self.limit = limit_per_minute
        # id -> [timestamp, tokens]. Reservations are mutated in place rather
        # than offset with a compensating negative entry: a correction appended
        # later carries a later timestamp, so it would outlive the reservation
        # it cancels and leave the window under-counted at the edges.
        self._events: dict[int, list] = {}
        self._next_id = 0
        self._lock = asyncio.Lock()

    def _evict(self, now: float) -> None:
        cutoff = now - _WINDOW_SECONDS
        for key in [k for k, (ts, _) in self._events.items() if ts < cutoff]:
            del self._events[key]

    def _in_window(self) -> int:
        return sum(t for _, t in self._events.values())

    async def try_acquire(self, tokens: int) -> int | None:
        """Reserve without blocking. Returns a reservation id, or None if full."""
        tokens = min(tokens, self.limit)
        async with self._lock:
            now = time.monotonic()
            self._evict(now)
            if self._in_window() + tokens <= self.limit:
                self._next_id += 1
                self._events[self._next_id] = [now, tokens]
                return self._next_id
            return None

    async def wait_hint(self, tokens: int) -> float:
        """Seconds until `tokens` could plausibly fit. 0.0 if they fit now."""
        tokens = min(tokens, self.limit)
        async with self._lock:
            now = time.monotonic()
            self._evict(now)
            if self._in_window() + tokens <= self.limit:
                return 0.0
            if not self._events:
                return 0.0
            oldest_ts = min(ts for ts, _ in self._events.values())
            return max(0.05, (oldest_ts + _WINDOW_SECONDS) - now)

    async def headroom(self) -> int:
        async with self._lock:
            self._evict(time.monotonic())
            return self.limit - self._in_window()

    async def acquire(self, tokens: int) -> int:
        """
        Block until `tokens` fit inside the rolling window, then reserve them.
        Returns a reservation id for reconcile()/release().
        """
        while True:
            reservation = await self.try_acquire(tokens)
            if reservation is not None:
                return reservation
            wait = await self.wait_hint(tokens)
            log.info(
                "TPM bucket full (%d/%d free, need %d) — waiting %.1fs",
                await self.headroom(),
                self.limit,
                min(tokens, self.limit),
                wait,
            )
            await asyncio.sleep(min(wait, _WINDOW_SECONDS))

    async def reconcile(self, reservation: int, actual: int) -> None:
        """Shrink (or grow) a reservation to what the API actually billed."""
        async with self._lock:
            entry = self._events.get(reservation)
            if entry is not None:
                entry[1] = min(actual, self.limit)

    async def release(self, reservation: int) -> None:
        """Drop a reservation for a call that never reached the API."""
        async with self._lock:
            self._events.pop(reservation, None)

    async def penalise(self, seconds: float) -> None:
        """
        Mark this bucket saturated for roughly `seconds`.

        Called when the server returns 429: its accounting disagrees with ours
        and the server is authoritative. Without this, releasing the failed
        reservation made the bucket look *emptier*, so the router handed the
        same exhausted key straight back and the call 429'd again — the retry
        loop slept out its attempts on one key while the other keys in the pool
        sat idle.
        """
        async with self._lock:
            now = time.monotonic()
            self._evict(now)
            # Backdate the block so it expires ~`seconds` from now.
            stamp = now - max(0.0, _WINDOW_SECONDS - seconds)
            self._next_id += 1
            self._events[self._next_id] = [stamp, self.limit]


# Keyed by (model, api_key). Groq meters TPM per key AND per model, so each
# combination is an independent budget: two keys double the ceiling for the
# same model, and a second model doubles it again for the same key.
_buckets: dict[tuple[str, str], _TokenBucket] = {}


def _bucket_for(model: str, api_key: str = "") -> _TokenBucket:
    if api_key == "" and GROQ_API_KEYS:
        api_key = GROQ_API_KEYS[0]
    slot = (model, api_key)
    if slot not in _buckets:
        _buckets[slot] = _TokenBucket(GROQ_TPM_LIMIT)
    return _buckets[slot]


def reset_buckets() -> None:
    """Drop all rate-limit state. Used by tests."""
    _buckets.clear()


async def _acquire_slot(model: str, tokens: int) -> tuple[str, int]:
    """
    Reserve capacity on whichever key has room for this model.

    Single key: identical to waiting on that one bucket. Multiple keys: fans
    out across independent budgets, so N keys give N x the throughput without
    changing prompts, models, or output quality.
    """
    keys = GROQ_API_KEYS or [""]

    if len(keys) == 1:
        key = keys[0]
        return key, await _bucket_for(model, key).acquire(tokens)

    while True:
        # Prefer the emptiest bucket so load spreads instead of pinning key 1.
        ranked = sorted(
            [(await _bucket_for(model, k).headroom(), k) for k in keys],
            key=lambda pair: pair[0],
            reverse=True,
        )
        for _, key in ranked:
            reservation = await _bucket_for(model, key).try_acquire(tokens)
            if reservation is not None:
                return key, reservation

        hints = [await _bucket_for(model, k).wait_hint(tokens) for k in keys]
        wait = min(h for h in hints if h > 0) if any(h > 0 for h in hints) else 0.05
        log.info(
            "All %d keys saturated for %s (need %d) — waiting %.1fs",
            len(keys),
            model,
            tokens,
            wait,
        )
        await asyncio.sleep(min(wait, _WINDOW_SECONDS))


# ── Public API ───────────────────────────────────────────────────────────────


async def complete_json(
    system: str,
    user: str,
    *,
    model: str = GROQ_MODEL,
    temperature: float = GROQ_TEMPERATURE,
    max_tokens: int = GROQ_MAX_TOKENS,
) -> str:
    """
    Single chat completion in JSON mode. Returns the raw response string.

    Paces itself against the per-model TPM bucket and retries 429s with
    backoff. Raises the last error if every attempt is exhausted.
    """
    # Reserve input + the worst-case completion; reconciled against real usage
    # once the response comes back.
    estimated = _estimate_tokens(system) + _estimate_tokens(user) + max_tokens

    kwargs: dict = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if _supports_reasoning_effort(model):
        kwargs["reasoning_effort"] = GROQ_REASONING_EFFORT

    last_exc: Exception | None = None

    for attempt in range(1, GROQ_MAX_RETRIES + 1):
        api_key, reservation = await _acquire_slot(model, estimated)
        bucket = _bucket_for(model, api_key)
        try:
            response = await asyncio.wait_for(
                _get_client(api_key).chat.completions.create(**kwargs),
                timeout=GROQ_REQUEST_TIMEOUT_S,
            )
        except RateLimitError as exc:
            last_exc = exc
            delay = _retry_after_seconds(exc, attempt)
            # Trust the server over our estimate and take this key out of
            # rotation for the reset window. With a pool, the next acquire
            # lands on a different key immediately instead of sleeping here;
            # with one key, acquire() does the waiting.
            await bucket.release(reservation)
            await bucket.penalise(delay)
            if attempt == GROQ_MAX_RETRIES:
                log.warning("Groq rate limit on %s — retries exhausted", model)
                break
            log.warning(
                "Groq 429 on %s (attempt %d/%d) — key parked %.1fs, rerouting",
                model,
                attempt,
                GROQ_MAX_RETRIES,
                delay,
            )
            continue
        except asyncio.TimeoutError as exc:
            last_exc = exc
            await bucket.release(reservation)
            if attempt == GROQ_MAX_RETRIES:
                log.error("Groq timed out on %s after %d attempts", model, attempt)
                break
            log.warning(
                "Groq call exceeded %.0fs on %s (attempt %d/%d) — retrying",
                GROQ_REQUEST_TIMEOUT_S, model, attempt, GROQ_MAX_RETRIES,
            )
            continue
        except Exception as exc:
            await bucket.release(reservation)
            raise exc

        usage = getattr(response, "usage", None)
        if usage is not None:
            await bucket.reconcile(reservation, usage.total_tokens)
        else:
            await bucket.release(reservation)

        choice = response.choices[0]
        if choice.finish_reason == "length":
            # Truncated output, almost always reasoning tokens eating the
            # budget. The salvaged half-object used to be handed on as if it
            # were a complete answer: _extract_json returns the partial text,
            # and if the braces happen to balance it validates into an advisory
            # missing whatever came after the cut — most often an empty
            # sources_cited, reported as a schema error that says nothing about
            # the real cause. Raising here routes it into the agent's normal
            # retry instead of shipping a half-written advisory.
            log.warning(
                "Groq response truncated on %s (max_tokens=%d, completion=%s) — "
                "raise GROQ_MAX_TOKENS or lower GROQ_REASONING_EFFORT",
                model,
                max_tokens,
                getattr(usage, "completion_tokens", "?"),
            )
            raise TruncatedCompletion(
                f"{model} hit max_tokens={max_tokens} before closing the JSON"
            )

        return choice.message.content or ""

    raise last_exc if last_exc else RuntimeError("Groq call failed with no exception")


def _retry_after_seconds(exc: Exception, attempt: int) -> float:
    """Prefer the server's Retry-After; otherwise exponential backoff + jitter."""
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None) or {}
    for key in ("retry-after", "x-ratelimit-reset-tokens", "x-ratelimit-reset-requests"):
        raw = headers.get(key)
        if not raw:
            continue
        seconds = _parse_duration(str(raw))
        if seconds is not None:
            return min(seconds + 0.25, _WINDOW_SECONDS)
    return min(2.0**attempt + random.uniform(0, 0.5), _WINDOW_SECONDS)


def _parse_duration(raw: str) -> float | None:
    """Parse Groq duration strings: '4.995s', '1m26.4s', '630ms', '12'."""
    raw = raw.strip()
    try:
        return float(raw)  # plain seconds
    except ValueError:
        pass
    total = 0.0
    matched = False
    number = ""
    i = 0
    while i < len(raw):
        ch = raw[i]
        if ch.isdigit() or ch == ".":
            number += ch
            i += 1
            continue
        if not number:
            return None
        value = float(number)
        number = ""
        if raw.startswith("ms", i):
            total += value / 1000.0
            i += 2
        elif ch == "s":
            total += value
            i += 1
        elif ch == "m":
            total += value * 60.0
            i += 1
        elif ch == "h":
            total += value * 3600.0
            i += 1
        else:
            return None
        matched = True
    return total if matched else None
