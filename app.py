"""
Hugging Face Space entry point — `sdk: gradio`.

Why this file exists
--------------------
Docker Spaces now require a paid plan; Gradio Spaces on ZeroGPU are still free
for personal accounts. So the API is served *through* the Gradio SDK instead of
a Dockerfile. `docs/HOW_TO_DEPLOY_BACKEND.md` describes the old Docker route and
is kept for the day that becomes affordable again.

Nothing about the backend changes. `gr.mount_gradio_app` mounts the Gradio UI
*into* the existing FastAPI app rather than the other way round, so every route
keeps the exact path the frontend already calls:

    /api/*      /health/*      /metrics      /ws/stream       unchanged
    /ui                                                       Gradio status page

That matters: `VITE_API_URL` points at the Space origin and nothing in
`frontend/src/api.js` needs a prefix.

Spaces runs this file as a script, the same way the ZeroGPU template's
`demo.launch()` works, so the uvicorn call under __main__ is what binds :7860.
"""

from __future__ import annotations

import logging
import os
import threading

import gradio as gr

# Importing backend.app runs backend/__init__.py first, which loads .env (absent
# here — the Space injects GROQ_API_KEY as a real environment variable) and pins
# the TF/loky settings every entry point needs.
from backend.app import app as helioops

log = logging.getLogger(__name__)


def _prewarm_embedder() -> None:
    """
    Pull BAAI/bge-small-en-v1.5 into the HF cache in the background.

    The Docker image baked this at build time. There is no build step here, so
    the first retrieval would otherwise pay a ~90s download — inside the first
    /api/detect a judge runs. Done on a daemon thread rather than at import so
    the port binds immediately and the Space reports healthy while the model
    downloads.
    """
    try:
        from backend.embeddings.embedder import embed_query

        embed_query("warm")
        log.info("embedder prewarmed")
    except Exception as exc:  # never block serving on a cache warm
        log.warning("embedder prewarm skipped: %s", exc)


with gr.Blocks(title="HelioOps API") as demo:
    gr.Markdown(
        """
        # HelioOps API

        Space-weather operations backend — CME detection, quantile impact
        prediction, four RAG-grounded industry agents, and a deterministic
        verifier that rewrites unsafe values before an operator sees them.

        This Space is the **API**, not the console. The operator UI lives on the
        frontend deployment and calls this origin.

        | Endpoint | What it does |
        |---|---|
        | `GET /health/ready` | readiness — `knowledge_base: false` means RAG is dead |
        | `GET /api/storms` | replayable storms + completed runs |
        | `POST /api/detect/{storm_id}` | full pipeline, 65–80s |
        | `GET /api/result/{storm_id}` | last result for a storm |
        | `WS /ws/stream` | live pipeline events |
        | `GET /docs` | OpenAPI |
        """
    )

# Gradio mounts INTO the API app, not the reverse — the backend keeps every path.
app = gr.mount_gradio_app(helioops, demo, path="/ui")


if __name__ == "__main__":
    import uvicorn

    threading.Thread(target=_prewarm_embedder, daemon=True).start()

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT") or os.getenv("GRADIO_SERVER_PORT") or 7860),
    )
