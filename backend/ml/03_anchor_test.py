"""
Physics anchor test for the served checkpoints.

    PYTHONPATH=. python backend/ml/03_anchor_test.py

Goes through backend.ml.inference.predict() rather than loading the pkls
directly, so it exercises the exact code path the API serves — feature
extraction, quantile ordering and clipping included. Loading the models here
separately would let training/serving skew pass this gate unnoticed.

Exits non-zero on failure. The previous version caught its own AssertionError
and printed "[FAIL]" while exiting 0, so it could not gate anything: a
regression looked identical to a pass to CI, to a shell `&&`, and to anyone
skimming the output.
"""

from __future__ import annotations

import sys

from backend.ml.inference import predict

# Two anchors, chosen so the test measures ordering as well as magnitude.
# A model that returns a constant passes any single-storm threshold.
ANCHORS = [
    {
        "name": "2024-05 G5 (Gannon)",
        "event": {
            "scales": {"G": 5, "R": 3},
            "cme": {"speed_km_s": 1800.0, "angular_width_deg": 180.0},
            "l1_solar_wind": {"bz_nt": -40.0, "speed_km_s": 850.0},
        },
        # Severe-storm floors. Both derive from the generator's rules in
        # 01_data_generation_eda.py, not from measured 2024 outcomes.
        "min_gps_error_m": 15.0,
        "min_hf_prob": 0.80,
    },
    {
        "name": "quiet baseline (G0/R0)",
        "event": {
            "scales": {"G": 0, "R": 0},
            "cme": {"speed_km_s": 400.0, "angular_width_deg": 30.0},
            "l1_solar_wind": {"bz_nt": 2.0, "speed_km_s": 350.0},
        },
        "max_gps_error_m": 2.0,
        "max_hf_prob": 0.60,
    },
]


def check(label: str, ok: bool, detail: str) -> bool:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}: {detail}")
    return ok


def main() -> int:
    print("Physics anchor test - backend/ml/checkpoints via inference.predict()\n")
    results, failures = {}, []

    for anchor in ANCHORS:
        p = predict(anchor["event"])
        results[anchor["name"]] = p
        print(f"{anchor['name']}")
        print(
            f"  GPS L1 error : {p.gps_error_m:7.2f} m  "
            f"[{p.gps_error_ci_low:.2f}, {p.gps_error_ci_high:.2f}]"
        )
        print(
            f"  HF blackout  : {p.hf_blackout_prob:7.2%}    "
            f"[{p.hf_blackout_ci_low:.2%}, {p.hf_blackout_ci_high:.2%}]"
        )

        if "min_gps_error_m" in anchor:
            lo = anchor["min_gps_error_m"]
            if not check("GPS error above severe floor", p.gps_error_m > lo,
                         f"{p.gps_error_m:.2f} m > {lo} m"):
                failures.append(anchor["name"])
            hi = anchor["min_hf_prob"]
            if not check("HF probability above severe floor", p.hf_blackout_prob > hi,
                         f"{p.hf_blackout_prob:.2%} > {hi:.0%}"):
                failures.append(anchor["name"])
        else:
            lo = anchor["max_gps_error_m"]
            if not check("GPS error stays quiet", p.gps_error_m < lo,
                         f"{p.gps_error_m:.2f} m < {lo} m"):
                failures.append(anchor["name"])
            hi = anchor["max_hf_prob"]
            if not check("HF probability stays quiet", p.hf_blackout_prob < hi,
                         f"{p.hf_blackout_prob:.2%} < {hi:.0%}"):
                failures.append(anchor["name"])

        # A quantile model whose interval does not bracket its own median is
        # broken regardless of magnitude.
        if not check(
            "quantiles ordered",
            p.gps_error_ci_low <= p.gps_error_m <= p.gps_error_ci_high
            and p.hf_blackout_ci_low <= p.hf_blackout_prob <= p.hf_blackout_ci_high,
            "q025 <= q500 <= q975 for both targets",
        ):
            failures.append(anchor["name"])
        print()

    severe = results["2024-05 G5 (Gannon)"]
    quiet = results["quiet baseline (G0/R0)"]
    print("Ordering")
    if not check("G5 impact exceeds quiet baseline",
                 severe.gps_error_m > quiet.gps_error_m
                 and severe.hf_blackout_prob > quiet.hf_blackout_prob,
                 f"GPS {severe.gps_error_m:.2f} > {quiet.gps_error_m:.2f} m, "
                 f"HF {severe.hf_blackout_prob:.2%} > {quiet.hf_blackout_prob:.2%}"):
        failures.append("ordering")

    if failures:
        print(f"\nANCHOR TEST FAILED ({len(failures)} check(s)): {sorted(set(failures))}")
        return 1
    print("\nANCHOR TEST PASSED - checkpoints reproduce the physics ordering.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
