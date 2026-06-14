# Runbook: High Latency (p99 > 500ms)

**Alert**: `HighLatency`
**Severity**: Warning
**SLO Impact**: Yes — p99 exceeds 500ms threshold

## Immediate Steps

1. Check current latency metrics:
   ```bash
   curl -s https://api.helioops.example.com/metrics | grep duration
   ```

2. Check pod resource usage:
   ```bash
   kubectl top pods -l app=helioops,component=backend -n production
   ```

3. Check if HPA is scaling:
   ```bash
   kubectl get hpa -n production
   ```

4. Identify slow pipeline stage:
   ```bash
   kubectl logs -l app=helioops,component=backend --tail=100 -n production | \
     grep "pipeline_completed" | jq '.duration_seconds'
   ```

5. Check Groq API latency (most common bottleneck):
   ```bash
   kubectl logs -l app=helioops,component=backend --tail=100 -n production | \
     grep "advisory_generation" | tail -20
   ```

## Mitigation

- If Groq is slow: Pipeline degrades gracefully; advisories use cached responses
- If ML models are slow: Check checkpoint loading (`/health/ready` → `ml_models: true`)
- If memory pressure: Increase pod memory limit or add HPA

## Escalation

- If p99 > 5s for 10 minutes: Scale horizontally
  ```bash
  kubectl scale deploy/helioops-backend --replicas=5 -n production
  ```