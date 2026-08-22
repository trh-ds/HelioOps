"""
tests/test_ask.py — the per-agent operator chatbot.

Nothing here touches the network: complete_json is patched everywhere, because
the point of these tests is the contract around the call, not the model.
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.genai.ask import answer_question
from backend.genai.models import RetrievedChunk

client = TestClient(app, raise_server_exceptions=False)


def _chunks(source="nat_doc_007_2025.pdf", page=42):
    return [
        RetrievedChunk(
            chunk_id="c1",
            text="Switch to 5 MHz for polar operations.",
            source=source,
            similarity=0.81,
            metadata={"page": page},
        )
    ]


class TestAnswerQuestion:
    def test_unknown_industry_raises(self):
        with pytest.raises(ValueError, match="Unknown industry"):
            asyncio.run(answer_question("banking", "what now?"))

    def test_empty_question_raises(self):
        with pytest.raises(ValueError, match="empty"):
            asyncio.run(answer_question("aviation", "   "))

    def test_returns_parsed_shape(self):
        payload = '{"answer": "Use 5 MHz.", "sources_cited": ["nat_doc_007_2025.pdf p.42"]}'
        with patch("backend.genai.ask.retrieve_chunks", return_value=_chunks()), patch(
            "backend.genai.ask.complete_json", return_value=payload
        ):
            out = asyncio.run(answer_question("aviation", "which HF band?"))
        assert out["answer"] == "Use 5 MHz."
        assert out["sources_cited"] == ["nat_doc_007_2025.pdf p.42"]

    def test_runs_on_the_checker_model(self):
        """Chat must not spend the advisory model's TPM bucket."""
        from backend.genai.config import GROQ_CHECKER_MODEL

        payload = '{"answer": "ok", "sources_cited": []}'
        with patch("backend.genai.ask.retrieve_chunks", return_value=_chunks()), patch(
            "backend.genai.ask.complete_json", return_value=payload
        ) as call:
            asyncio.run(answer_question("aviation", "which HF band?"))
        assert call.call_args.kwargs["model"] == GROQ_CHECKER_MODEL

    def test_invented_source_is_dropped(self):
        """A citation the retrieval never returned must not reach the operator -
        they would click it and get a 404 from /api/kb/source."""
        payload = '{"answer": "x", "sources_cited": ["totally_made_up.pdf p.9"]}'
        with patch("backend.genai.ask.retrieve_chunks", return_value=_chunks()), patch(
            "backend.genai.ask.complete_json", return_value=payload
        ):
            out = asyncio.run(answer_question("aviation", "q"))
        assert out["sources_cited"] == []

    def test_llm_failure_degrades_instead_of_raising(self):
        with patch("backend.genai.ask.retrieve_chunks", return_value=_chunks()), patch(
            "backend.genai.ask.complete_json", side_effect=RuntimeError("groq down")
        ):
            out = asyncio.run(answer_question("aviation", "q"))
        assert "could not reach" in out["answer"].lower()
        assert out["sources_cited"] == []

    def test_advisory_context_is_included(self):
        payload = '{"answer": "ok", "sources_cited": []}'
        advisory = {
            "advisory": {
                "severity": "CRITICAL",
                "summary": "Polar routes degraded",
                "action_items": [
                    {"step": 1, "action": "Switch HF to 5 MHz", "source_ref": "nat_doc_007_2025.pdf"}
                ],
            }
        }
        with patch("backend.genai.ask.retrieve_chunks", return_value=_chunks()), patch(
            "backend.genai.ask.complete_json", return_value=payload
        ) as call:
            asyncio.run(answer_question("aviation", "why?", advisory))
        user_msg = call.call_args.args[1]
        assert "Polar routes degraded" in user_msg
        assert "Switch HF to 5 MHz" in user_msg


class TestAskEndpoint:
    def _reset_limit(self):
        from backend import middleware

        middleware._ask_calls.clear()

    def test_unknown_industry_returns_400(self):
        self._reset_limit()
        resp = client.post("/api/ask", json={"industry": "banking", "question": "hi there"})
        assert resp.status_code == 400

    def test_empty_question_returns_422(self):
        """Pydantic's min_length rejects it before the route runs."""
        self._reset_limit()
        resp = client.post("/api/ask", json={"industry": "aviation", "question": ""})
        assert resp.status_code == 422

    def test_returns_answer(self):
        self._reset_limit()
        payload = '{"answer": "Use 5 MHz.", "sources_cited": []}'
        with patch("backend.genai.ask.retrieve_chunks", return_value=_chunks()), patch(
            "backend.genai.ask.complete_json", return_value=payload
        ):
            resp = client.post(
                "/api/ask", json={"industry": "aviation", "question": "which HF band?"}
            )
        assert resp.status_code == 200
        assert resp.json()["answer"] == "Use 5 MHz."

    def test_second_call_inside_window_is_rate_limited(self):
        self._reset_limit()
        payload = '{"answer": "ok", "sources_cited": []}'
        with patch("backend.genai.ask.retrieve_chunks", return_value=_chunks()), patch(
            "backend.genai.ask.complete_json", return_value=payload
        ):
            body = {"industry": "aviation", "question": "which HF band?"}
            assert client.post("/api/ask", json=body).status_code == 200
            assert client.post("/api/ask", json=body).status_code == 429

    def test_rate_limit_does_not_block_a_different_client(self):
        self._reset_limit()
        from backend import middleware

        middleware._ask_calls["1.2.3.4"] = middleware.time.time()
        payload = '{"answer": "ok", "sources_cited": []}'
        with patch("backend.genai.ask.retrieve_chunks", return_value=_chunks()), patch(
            "backend.genai.ask.complete_json", return_value=payload
        ):
            resp = client.post(
                "/api/ask", json={"industry": "aviation", "question": "which HF band?"}
            )
        assert resp.status_code == 200
