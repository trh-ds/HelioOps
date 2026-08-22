"""
Smoke-test a deployed HelioOps Space (or any API origin).

    python deployment/smoke_space.py https://trh-ds-helioops-api.hf.space

Checks the four things that can each fail silently, in the order they will bite
you. The WebSocket check is the one worth watching: mounting the API under the
Gradio SDK is not a configuration HF documents, so /ws/stream surviving the
Spaces proxy is exactly what this is here to prove or disprove.

Exit code is the number of failed checks, so CI can gate on it.
"""

from __future__ import annotations

import json
import sys
import urllib.request

TIMEOUT = 30


def _get(url: str) -> tuple[int, dict | str]:
    req = urllib.request.Request(url, headers={"User-Agent": "helioops-smoke"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read().decode()
            try:
                return r.status, json.loads(body)
            except json.JSONDecodeError:
                return r.status, body[:200]
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, body[:200]
    except Exception as e:  # noqa: BLE001 - any transport failure is a failure
        return 0, str(e)


def check_health(base: str) -> bool:
    # /health/ready answers 503 with the SAME body shape when degraded, so parse
    # unconditionally rather than trusting the status code.
    status, body = _get(f"{base}/health/ready")
    if not isinstance(body, dict) or "checks" not in body:
        print(f"  FAIL  /health/ready unreadable (status {status}): {body}")
        return False

    checks = body["checks"]
    print(f"  status={body.get('status')}  {checks}")

    # The one that matters. A permissions or path failure on ChromaDB does not
    # raise: retrieve_chunks() swallows it and every advisory goes ungrounded
    # while still looking confident and well-formed.
    if not checks.get("knowledge_base"):
        print("  FAIL  knowledge_base is false - RAG is dead, advisories will be ungrounded")
        return False
    if not all(checks.values()):
        print(f"  FAIL  a dependency is down: {checks}")
        return False
    print("  ok    all dependency checks green")
    return True


def check_storms(base: str) -> bool:
    status, body = _get(f"{base}/api/storms")
    if status != 200 or not isinstance(body, dict):
        print(f"  FAIL  /api/storms status {status}: {body}")
        return False
    storms = body.get("available_storms") or []
    if not storms:
        print("  FAIL  no available storms")
        return False
    print(f"  ok    {len(storms)} storms: {', '.join(storms)}")
    return True


def check_docs(base: str) -> bool:
    """Proves the FastAPI app is what is serving, not Gradio's own root."""
    status, _ = _get(f"{base}/docs")
    if status != 200:
        print(f"  FAIL  /docs status {status} - the API may not be mounted")
        return False
    print("  ok    FastAPI is serving (the mount worked)")
    return True


def check_websocket(base: str) -> bool:
    try:
        from websockets.sync.client import connect
    except ImportError:
        print("  SKIP  pip install websockets to test /ws/stream")
        return True

    ws_url = base.replace("https://", "wss://").replace("http://", "ws://") + "/ws/stream"
    try:
        # Connect only. Sending run_pipeline would burn 25s of Groq budget and a
        # rate-limit slot; the question here is whether the proxy upgrades at all.
        with connect(ws_url, open_timeout=TIMEOUT):
            print("  ok    /ws/stream upgraded - live streaming works")
            return True
    except Exception as e:  # noqa: BLE001
        print(f"  FAIL  /ws/stream did not upgrade: {type(e).__name__}: {e}")
        print("        The console falls back to 'Run batch (REST)'; live mode is dead.")
        return False


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    base = sys.argv[1].rstrip("/")
    print(f"Smoke-testing {base}\n")

    failures = 0
    for name, fn in (
        ("FastAPI mounted", check_docs),
        ("health", check_health),
        ("storms", check_storms),
        ("websocket", check_websocket),
    ):
        print(f"{name}:")
        if not fn(base):
            failures += 1
        print()

    print("PASS" if not failures else f"{failures} check(s) FAILED")
    return failures


if __name__ == "__main__":
    raise SystemExit(main())
