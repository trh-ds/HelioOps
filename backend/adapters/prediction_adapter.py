"""
MLPredictionAdapter — wraps ML_after_CV.inference behind the PredictionPort interface.

FallbackPredictionAdapter returns conservative defaults when models are unavailable.
"""

from __future__ import annotations

from typing import Any

from backend.logging import get_logger
from backend.ports.prediction import PredictionPort

log = get_logger("backend.adapters.prediction")


class MLPredictionAdapter(PredictionPort):
    def __init__(self):
        self._models_loaded = False

    def predict(self, storm_dict: dict) -> Any:
        from ML_after_CV.inference import predict
        result = predict(storm_dict)
        self._models_loaded = True
        log.info(
            "prediction_completed",
            gps_error_m=result.gps_error_m,
            hf_blackout_prob=result.hf_blackout_prob,
        )
        return result

    async def predict_async(self, storm_dict: dict) -> Any:
        import asyncio
        return await asyncio.to_thread(self.predict, storm_dict)

    def is_available(self) -> bool:
        try:
            from ML_after_CV.inference import _load_models
            _load_models()
            from ML_after_CV.inference import _MODELS
            return len(_MODELS) >= 6
        except Exception:
            return False


class FallbackPredictionAdapter(PredictionPort):
    def __init__(self):
        from pydantic import BaseModel
        from ML_after_CV.inference import ImpactPrediction

        class _Fallback(BaseModel):
            gps_error_m: float = 20.0
            gps_error_ci_low: float = 8.0
            gps_error_ci_high: float = 35.0
            hf_blackout_prob: float = 0.85
            hf_blackout_ci_low: float = 0.60
            hf_blackout_ci_high: float = 0.95

        self._model = _Fallback

    def predict(self, storm_dict: dict) -> Any:
        log.warning("prediction_fallback", message="Using conservative defaults")
        return self._model()

    def is_available(self) -> bool:
        return True