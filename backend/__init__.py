"""
HelioOps backend.

.env is loaded here, not in app.py: importing any `backend.*` module runs this
first, so CLIs, ingest scripts, workers and tests all get the same environment
the API server does. Previously only `backend/app.py` called load_dotenv(), so
GROQ_API_KEY was silently empty for every other entry point.
"""

import os
from pathlib import Path

# Keep TensorFlow out of the process.
#
# The only model we load is BAAI/bge-small-en-v1.5 through sentence-transformers,
# which runs on torch. transformers nevertheless probes for TensorFlow and
# imports it when it is installed, which it is on developer machines as a
# transitive dependency. That cost ~500MB of RSS (963MB total after loading the
# embedder, against ~400MB with torch alone) and several seconds per process,
# for a framework nothing here calls. It is not in backend/requirements.txt, so
# this is dev-machine and CI bloat only — but every test run and every local
# demo paid it.
#
# embeddings/embedder.py already set TRANSFORMERS_NO_TF, but two things made it
# ineffective: current transformers reads USE_TF, and by the time that module
# is imported something else may already have pulled transformers in. Setting
# both here means any `import backend.*` wins the race.
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("USE_TORCH", "1")
# Silences the oneDNN/cuda banner if something else does drag TF in.
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

# joblib probes physical core count by shelling out to `wmic`, which Windows 11
# build 26xxx no longer ships. The failure is non-fatal but dumps a full
# subprocess traceback into the output of every ML run and every test session.
# loky only skips the probe when LOKY_MAX_CPU_COUNT is STRICTLY BELOW
# os.cpu_count() (see loky/backend/context.py: `if cpu_count_user <
# os_cpu_count: return`), so setting it to the logical count -- as this did --
# left the probe, the warning and the traceback firing every run.
# ponytail: logical//2 is the physical count on any SMT machine and is exactly
# what the probe was looking for; on a non-SMT host it under-subscribes by 2x.
# Read the real topology only if joblib parallelism ever becomes a bottleneck.
os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(max(1, (os.cpu_count() or 2) // 2)))

from dotenv import load_dotenv  # noqa: E402 — must follow the env setup above

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
