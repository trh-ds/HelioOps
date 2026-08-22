"""Stage 3 — assemble the CV layer's output artifact.

fusion — StormEvent schema + fuse(): weighted confidence, NOAA G/S/R scales,
         L1 arrival ETA, timeline. Single source of truth for the contract.
detect — orchestrator + CLI. Runs stages 1-2 for a storm_id and returns a
         StormEvent, with a stub fallback at every step.
"""
