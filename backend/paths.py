"""
Every runtime path, resolved from this file — never from the current directory.

Before this existed, `embeddings/config.py` used "./data/chroma_db" while
`genai/config.py` computed an absolute path, so ingest and retrieval could
silently target two different databases depending on where you launched from.
Same class of bug for the CV caches and the ML checkpoints in a container
whose WORKDIR is not the repo root.
"""

from pathlib import Path

BACKEND_DIR = Path(__file__).parent
DATA_DIR = BACKEND_DIR / "data"

CHROMA_DIR = DATA_DIR / "chroma_db"
CACHE_DIR = DATA_DIR / "cached"
STUBS_DIR = BACKEND_DIR / "cv" / "stubs"
CHECKPOINT_DIR = BACKEND_DIR / "ml" / "checkpoints"

# The synthetic training set and the EDA plots built from it. The training
# scripts used bare "data/" and "checkpoints/", so they only worked from
# inside backend/ml and silently did nothing from the repo root that README
# tells you to run them from.
ML_DATA_DIR = BACKEND_DIR / "ml" / "data"
SYNTHETIC_CSV = ML_DATA_DIR / "synthetic_storms.csv"
EDA_DIR = ML_DATA_DIR / "eda_plots"
