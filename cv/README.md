# cv/ — Computer Vision Detection Layer

Deterministic CME (Coronal Mass Ejection) detection pipeline using NASA DONKI physics and CCOR-1/LASCO coronagraph imagery.

## Architecture

```
detect(storm_id)
  ├── preprocessing.py    Load + normalize PNGs, running-difference frames
  ├── threshold_detector   Radial-profile CME detection (no CNN)
  ├── donki_client.py      NASA DONKI API → speed, angular width, direction
  ├── flare_classifier.py  GOES XRS flare class (X/M/C) + R-scale
  ├── l1_client.py         L1 solar wind (Bz, Bt, density, speed)
  └── fusion.py            Weighted fusion → StormEvent (conf = 0.4·det + 0.2·flare + 0.2·wind + 0.2·cme)
```

## Key Design (Option C)

Replaced CNN-based approach with **deterministic threshold detection** + NASA DONKI real physics. Reasons:
- No labeled training data for coronagraph CME detection
- DONKI provides authoritative kinematics (speed, width, direction)
- Deterministic = reproducible, testable, no GPU needed

## Fallback Chain

Every layer has safe fallback:
1. PNGs exist → use them, else → need `cache_fits.py`
2. Detector finds CME → real bbox, else → stub bbox_norm
3. DONKI cache exists → real physics, else → fetch live → fail → stub speed
4. StormEvent built → return it, else → load stub JSON from `ml/stubs/`

## Files

| File | Purpose |
|------|---------|
| `detect.py` | Entry point — `detect(storm_id)` and `detect_live()` |
| `preprocessing.py` | PNG loading, normalization, running-difference |
| `threshold_detector.py` | Radial-profile CME detection |
| `donki_client.py` | NASA DONKI API client (speed, width, direction) |
| `flare_classifier.py` | GOES XRS flare classification |
| `l1_client.py` | L1 solar wind measurements |
| `fusion.py` | Multi-source fusion → `StormEvent` model |
| `cache_fits.py` | FITS→PNG conversion utility |

## Output: `StormEvent`

```python
StormEvent(
    storm_id="2024-10-G4",
    confidence=0.91,
    scales={"G": 4, "S": 2, "R": 3},
    cme={speed_km_s, angular_width_deg, direction, ...},
    flare={class, r_scale, onset, ...},
    l1_solar_wind={bz_nt, speed_km_s, density_cm3, ...},
    timeline=[...],
    noaa_alert_raw="G4 Watch Kp 8.3"
)
```

## Usage

```bash
python -m cv.detect --storm 2024-10-G4
python -m cv.detect --storm 2024-05-G5
```
