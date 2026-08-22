#!/bin/bash
# Bootstraps the HelioOps box. Runs once on first boot, and again whenever
# Terraform replaces the instance (user_data_replace_on_change).
#
# Output lands in /var/log/cloud-init-output.log. If the API is not answering,
# read that before anything else.
set -euxo pipefail

dnf update -y
dnf install -y docker

# Compose v2 ships as a CLI plugin, not a package, on AL2023.
mkdir -p /usr/local/lib/docker/cli-plugins
curl -sSL "https://github.com/docker/compose/releases/download/v2.32.4/docker-compose-linux-x86_64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

systemctl enable --now docker

# 2 GB of swap. t3.small has 2 GB of RAM and the app sits near 1 GB RSS once
# torch and the bge-small embedder are loaded, so the headroom is thin during
# an /api/detect fan-out. Swap turns an OOM-kill into a slow request, which is
# the trade you want on a demo box. Drop it if you move to t3.medium.
if [ ! -f /swapfile ]; then
  dd if=/dev/zero of=/swapfile bs=1M count=2048
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >>/etc/fstab
fi

install -d -m 0755 /opt/helioops
cd /opt/helioops

# The compose file and Caddyfile are fetched from the running image rather than
# baked in here, so they stay in step with the repo. Simpler: write them at
# provision time from the templated values Terraform already has.
cat >/opt/helioops/.env <<EOF
HELIOOPS_IMAGE=${image}
HELIOOPS_DOMAIN=${domain}
HELIOOPS_CORS_ORIGINS=${cors_origins}
EOF

# The Groq key is read at deploy time, not baked into the AMI or user_data.
# user_data is visible to anyone who can call DescribeInstanceAttribute.
cat >/opt/helioops/fetch-secret.sh <<'EOS'
#!/bin/bash
set -euo pipefail
KEY=$(aws ssm get-parameter --name "PARAM_PATH" --with-decryption \
  --region "REGION" --query 'Parameter.Value' --output text)
grep -v '^GROQ_API_KEY=' /opt/helioops/.env >/opt/helioops/.env.tmp || true
echo "GROQ_API_KEY=$KEY" >>/opt/helioops/.env.tmp
mv /opt/helioops/.env.tmp /opt/helioops/.env
chmod 600 /opt/helioops/.env
EOS
sed -i "s|PARAM_PATH|${param_path}|; s|REGION|${region}|" /opt/helioops/fetch-secret.sh
chmod +x /opt/helioops/fetch-secret.sh

# Pull-and-restart. CI calls this over SSM; nothing here needs SSH.
cat >/opt/helioops/deploy.sh <<'EOS'
#!/bin/bash
set -euxo pipefail
cd /opt/helioops
/opt/helioops/fetch-secret.sh
source /opt/helioops/.env
REGISTRY="$${HELIOOPS_IMAGE%%/*}"
aws ecr get-login-password --region REGION | docker login --username AWS --password-stdin "$REGISTRY"
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
# The old ~3 GB image is dead weight once the new one is running.
docker image prune -af --filter "until=168h"
EOS
sed -i "s|REGION|${region}|" /opt/helioops/deploy.sh
chmod +x /opt/helioops/deploy.sh

# Compose file + Caddyfile are shipped inside the image at /app/deployment so a
# fresh box never needs the git repo. Extract them before the first run.
/opt/helioops/fetch-secret.sh
source /opt/helioops/.env
REGISTRY="$${HELIOOPS_IMAGE%%/*}"
aws ecr get-login-password --region ${region} | docker login --username AWS --password-stdin "$REGISTRY"
docker pull "$HELIOOPS_IMAGE"
CID=$(docker create "$HELIOOPS_IMAGE")
docker cp "$CID:/app/deployment/docker-compose.prod.yml" /opt/helioops/docker-compose.prod.yml
docker cp "$CID:/app/deployment/Caddyfile" /opt/helioops/Caddyfile
docker rm "$CID"

/opt/helioops/deploy.sh
