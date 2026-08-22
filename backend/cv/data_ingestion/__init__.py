"""Stage 1 — acquire every external input the CV layer consumes.

cache_fits       — coronagraph FITS frames (CCOR-1 via S3, LASCO via sunpy/VSO)
donki_client     — NASA DONKI CME analyses (speed, width, arrival estimate)
flare_classifier — GOES XRS X-ray flux → flare class + R-scale
l1_client        — DSCOVR L1 solar wind (speed, Bz, density)

All clients are cache-first and fall back to cached JSON on network failure.
"""
