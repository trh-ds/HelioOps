# Runbook: High Error Rate

**Alert**: `HighErrorRate`
**Severity**: Critical
**SLO Impact**: Yes — errors burn error budget

## Immediate Steps

1. Check recent deployments:
   ```bash
   kubectl rollout history deploy/helioops-backend -n staging
   kubectl rollout history deploy/helioops-backend -n production
   ```

2. Check error logs:
   ```bash
   kubectl logs -l app=helioops,component=backend --tail=200 -n staging | grep ERROR
   kubectl logs -l app=helioops,component=backend --tail=200 -n production | grep ERROR
   ```

3. Check downstream health:
   ```bash
   curl -s https://api.helioops.example.com/health/ready | jq .
   ```

4. Check ML model availability:
   ```bash
   curl -s https://api.helioops.example.com/health/ready | jq '.checks.ml_models'
   ```

## Rollback

```bash
kubectl rollout undo deploy/helioops-backend -n production
```

## Escalation

- If rollback doesn't resolve: Check Groq API status (https://status.groq.com)
- If Groq is down: Switch to fallback prediction adapter (automatic, check `/health/ready`)
- If ChromaDB is unreachable: Check persistent volume status