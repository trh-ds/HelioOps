# Runbook: GenAI / Groq API Outage

**Alert**: `AdvisoryGenerationFailed`
**Severity**: Critical
**SLO Impact**: Yes — no advisories generated

## Symptoms

- `advisory_generation_failed` in structured logs
- All advisory endpoints return empty lists
- WebSocket streams show `agent.error` events

## Immediate Steps

1. Verify Groq API status:
   ```bash
   curl -s https://api.groq.com/openai/v1/models -H "Authorization: Bearer $GROQ_API_KEY" | head -5
   ```

2. Check rate limiting:
   ```bash
   kubectl logs -l app=helioops,component=backend --tail=200 -n production | \
     grep "rate_limit\|429"
   ```

3. Check ChromaDB (RAG dependency):
   ```bash
   kubectl exec -it deploy/helioops-backend -n production -- \
     ls -la data/chroma_db/
   ```

## Mitigation

### If Groq is rate-limited (>429 errors):
- Reduce parallel advisory generation
- Increase `MAX_PROMPT_TOKENS` to reduce context size
- Switch to `GROQ_CHECKER_MODEL=llama-3.1-8b-instant` (lighter)

### If Groq is completely down:
- Pipeline continues without advisories (detection + ML still work)
- Verifier cannot run (depends on advisory output)
- Frontend shows detection + impact data but no advisory cards

### If ChromaDB is corrupted:
- Rebuild from source PDFs:
  ```bash
  python -m embeddings.build_index
  ```

## Escalation

- Monitor https://status.groq.com for service restoration
- If outage >30 min: Consider switching LLM provider (requires code change in `genai/config.py`)