# Runbook: Pipeline Detection Failure

**Alert**: `DetectionFailed`
**Severity**: Critical
**SLO Impact**: Yes — pipeline cannot proceed without detection

## Symptoms

- `/health/ready` returns `{ "checks": { "detection": false } }`
- Pipeline errors: `"Detection failed: ..."`

## Immediate Steps

1. Check if storm configurations are loadable:
   ```bash
   curl -s https://api.helioops.example.com/health/ready | jq '.checks.detection'
   ```

2. Check if cached FITS data exists:
   ```bash
   kubectl exec -it deploy/helioops-backend -n production -- \
     ls -la data/cached/ccor1/
   ```

3. Check DONKI API availability:
   ```bash
   curl -s "https://kauai.ccmc.gsfc.nasa.gov/DONKI/WS/get/CME?startDate=2024-10-08&endDate=2024-10-12" | head -20
   ```

4. Check logs for specific detection errors:
   ```bash
   kubectl logs -l app=helioops,component=backend --tail=200 -n production | \
     grep "detection_failed"
   ```

## Fallback Path

The detection pipeline has built-in fallback chains:
- PNG cache exists → use it
- PNG missing → use stub JSON directly
- DONKI fails → use stub speed/width

If all fallbacks fail, the pipeline returns an error response with detail.

## Resolution

- If cached data is missing: Re-run `cv.cache_fits` to populate cache
- If DONKI is down: Pipeline uses stubs automatically; no action needed
- If ongoing: Check upstream feeds (GOES XRS, DSCOVR)