"""
InMemoryResultRepository — dict-based result store for hackathon scope.

Future: swap this for PostgresResultRepository or RedisResultRepository
without changing any pipeline or API code.
"""

from __future__ import annotations

from typing import Any, Optional

import httpx

from backend.ports.repository import ResultRepository
from backend.pipeline import PipelineResult


class InMemoryResultRepository(ResultRepository):
    def __init__(self):
        self._results: dict[str, Any] = {}
        self._advisory_index: dict[str, dict] = {}

    def save(self, storm_id: str, result: Any) -> None:
        self._results[storm_id] = result

    def get(self, storm_id: str) -> Optional[Any]:
        return self._results.get(storm_id)

    def get_all(self) -> dict[str, Any]:
        return dict(self._results)

    def save_advisory(self, advisory_id: str, data: dict) -> None:
        self._advisory_index[advisory_id] = data

    def get_advisory(self, advisory_id: str) -> Optional[dict]:
        return self._advisory_index.get(advisory_id)


class SupabaseResultRepository(ResultRepository):
    """PostgREST-backed repository for Supabase tables."""

    def __init__(
        self,
        url: str,
        anon_key: str,
        *,
        pipeline_results_table: str = "pipeline_runs",
        advisories_table: str = "advisories",
        verified_advisories_table: str = "verified_advisories",
        provenance_traces_table: str = "provenance_traces",
        timeout: float = 10.0,
    ):
        self.url = url.rstrip("/")
        self.pipeline_results_table = pipeline_results_table
        self.advisories_table = advisories_table
        self.verified_advisories_table = verified_advisories_table
        self.provenance_traces_table = provenance_traces_table
        self._client = httpx.Client(
            base_url=f"{self.url}/rest/v1",
            headers={
                "apikey": anon_key,
                "Authorization": f"Bearer {anon_key}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
            timeout=timeout,
        )

    def save(self, storm_id: str, result: Any) -> None:
        self._upsert(self.pipeline_results_table, self._pipeline_payload(storm_id, result), "storm_id")

    def get(self, storm_id: str) -> Optional[Any]:
        rows = self._select(
            self.pipeline_results_table,
            params={"storm_id": f"eq.{storm_id}", "limit": "1"},
        )
        if not rows:
            return None
        return self._pipeline_result_from_row(rows[0], *self._child_rows(storm_id))

    def get_all(self) -> dict[str, Any]:
        rows = self._select(self.pipeline_results_table)
        return {
            row["storm_id"]: self._pipeline_result_from_row(row, *self._child_rows(row["storm_id"]))
            for row in rows
            if row.get("storm_id")
        }

    def save_advisory(self, advisory_id: str, data: dict) -> None:
        base_payload = {
            "advisory_id": advisory_id,
        }
        advisory = data.get("advisory")
        if advisory:
            self._upsert(
                self.advisories_table,
                {
                    **base_payload,
                    "storm_event_id": advisory.get("storm_event_id") or data.get("storm_id"),
                    "industry": advisory.get("industry"),
                    "severity": advisory.get("severity"),
                    "confidence_score": advisory.get("confidence_score"),
                    "summary": advisory.get("summary"),
                    "sources_cited": advisory.get("sources_cited", []),
                    "validation_passed": advisory.get("validation_passed", False),
                    "generated_at": advisory.get("generated_at"),
                    "model_used": advisory.get("model_used", ""),
                    "safety_flags": advisory.get("safety_flags", []),
                    "generation_errors": advisory.get("generation_errors", []),
                },
                "advisory_id",
            )

        verified = data.get("verified_advisory", {})
        self._upsert(
            self.verified_advisories_table,
            {
                **base_payload,
                "storm_id": verified.get("storm_id") or data.get("storm_id"),
                "industry": verified.get("industry"),
                "severity": verified.get("severity"),
                "numbered_actions": verified.get("numbered_actions", []),
                "timing_window": verified.get("timing_window", {}),
                "technical_details": verified.get("technical_details", ""),
                "cited_procedure": verified.get("cited_procedure", {}),
                "provenance_ref": verified.get("provenance_ref"),
                "requires_human": verified.get("requires_human", False),
            },
            "advisory_id",
        )
        provenance = data.get("provenance_trace", {})
        self._upsert(
            self.provenance_traces_table,
            {
                **base_payload,
                "trace_id": provenance.get("trace_id"),
                "chain": provenance.get("chain", []),
            },
            "advisory_id",
        )

    def get_advisory(self, advisory_id: str) -> Optional[dict]:
        verified_rows = self._select(
            self.verified_advisories_table,
            params={"advisory_id": f"eq.{advisory_id}", "limit": "1"},
        )
        if not verified_rows:
            return None
        provenance_rows = self._select(
            self.provenance_traces_table,
            params={"advisory_id": f"eq.{advisory_id}", "limit": "1"},
        )
        verified_row = verified_rows[0]
        provenance_row = provenance_rows[0] if provenance_rows else {}
        return {
            "verified_advisory": verified_row,
            "provenance_trace": provenance_row,
        }

    def _legacy_save_advisory(self, advisory_id: str, data: dict) -> None:
        payload = {
            "advisory_id": advisory_id,
            "storm_id": data.get("storm_id"),
            "verified_advisory": data.get("verified_advisory", {}),
            "provenance_trace": data.get("provenance_trace", {}),
        }
        self._upsert("advisory_index", payload, "advisory_id")

    def _legacy_get_advisory(self, advisory_id: str) -> Optional[dict]:
        rows = self._select(
            "advisory_index",
            params={"advisory_id": f"eq.{advisory_id}", "limit": "1"},
        )
        if not rows:
            return None
        row = rows[0]
        return {
            "verified_advisory": row.get("verified_advisory", {}),
            "provenance_trace": row.get("provenance_trace", {}),
        }

    def _upsert(self, table: str, payload: dict, conflict_key: str) -> None:
        response = self._client.post(
            f"/{table}",
            params={"on_conflict": conflict_key},
            headers={"Prefer": "resolution=merge-duplicates,return=representation"},
            json=payload,
        )
        response.raise_for_status()

    def _select(self, table: str, params: Optional[dict[str, str]] = None) -> list[dict]:
        response = self._client.get(f"/{table}", params=params)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _pipeline_payload(storm_id: str, result: Any) -> dict:
        if hasattr(result, "model_dump"):
            data = result.model_dump(mode="json")
        else:
            data = dict(result)
        errors = data.get("errors", [])
        return {
            "storm_id": storm_id,
            "advisory_count": len(data.get("advisories", [])),
            "verified_count": len(data.get("verified_advisories", [])),
            "error_count": len(errors),
            "errors": errors,
            "completed_at": data.get("completed_at") or None,
        }

    def _child_rows(self, storm_id: str) -> tuple[list[dict], list[dict], list[dict]]:
        advisories = self._select(
            self.advisories_table,
            params={"storm_event_id": f"eq.{storm_id}"},
        )
        verified = self._select(
            self.verified_advisories_table,
            params={"storm_id": f"eq.{storm_id}"},
        )
        advisory_ids = [row["advisory_id"] for row in verified if row.get("advisory_id")]
        provenance = []
        for advisory_id in advisory_ids:
            provenance.extend(
                self._select(
                    self.provenance_traces_table,
                    params={"advisory_id": f"eq.{advisory_id}", "limit": "1"},
                )
            )
        return advisories, verified, provenance

    @staticmethod
    def _pipeline_result_from_row(
        row: dict,
        advisories: Optional[list[dict]] = None,
        verified_advisories: Optional[list[dict]] = None,
        provenance_traces: Optional[list[dict]] = None,
    ) -> PipelineResult:
        return PipelineResult(
            storm_id=row["storm_id"],
            cv_event=row.get("cv_event") or {},
            impact_prediction=row.get("impact_prediction"),
            genai_event=row.get("genai_event") or {},
            advisories=advisories if advisories is not None else row.get("advisories") or [],
            verified_advisories=(
                verified_advisories
                if verified_advisories is not None
                else row.get("verified_advisories") or []
            ),
            provenance_traces=(
                provenance_traces
                if provenance_traces is not None
                else row.get("provenance_traces") or []
            ),
            errors=row.get("errors") or [],
            completed_at=row.get("completed_at") or "",
        )
