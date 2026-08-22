# AWS infrastructure — PARKED, NOT WORKING AS COMMITTED

**Do not run `terraform apply` against this expecting a working deploy.**

This is a single-EC2 shape (ECR image, one instance running docker compose with
Caddy for TLS, Elastic IP, SSM Session Manager instead of SSH, no load balancer).
It was written when AWS was the plan and abandoned mid-way when the project moved
to a platform with a free tier. It is committed so the work is not lost, not
because it is finished.

## What is missing

`user_data.sh` bootstraps the box by extracting the runtime config out of the
container image:

```sh
docker cp "$CID:/app/deployment/docker-compose.prod.yml" /opt/helioops/
docker cp "$CID:/app/deployment/Caddyfile"               /opt/helioops/
```

Those paths do not exist in the image. `deployment/Dockerfile.backend` copies
only `backend/`. Finishing this needs one line in that Dockerfile:

```dockerfile
COPY deployment/docker-compose.prod.yml deployment/Caddyfile deployment/
```

## What was never tested

Nothing here has been applied. In particular:

- whether `t3.small` (2 GB + 2 GB swap) actually holds torch, the bge-small
  embedder and Chroma under an `/api/detect` fan-out — the sizing is reasoned
  from `backend/__init__.py`, not measured
- Caddy's ACME HTTP-01 issuance, which needs the domain resolving to the
  Elastic IP *before* the container starts
- the GitHub OIDC deploy role (`var.github_repo`), which is off by default

## Where the live deploy actually is

See `railway.json` at the repo root and `docs/HOW_TO_DEPLOY_BACKEND.md`.
