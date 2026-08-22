"""Stage 2 — turn raw FITS frames into a CME detection.

preprocessing      — FITS load, letterbox pad, log-scale, running difference,
                     CLAHE denoise, occulter-center detection, batch PNG export
threshold_detector — 9-step deterministic detector: annular mask → sigma
                     threshold → morphology → connected components → bbox,
                     CPA, angular width, confidence → annotated PNG

No trained weights, no RNG: same input frames → identical output every run.
"""
