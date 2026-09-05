#!/usr/bin/env bash
set -e

PORT=${1:-8888}
TOKEN=$(openssl rand -hex 24)

echo ""
echo -e "\033[1;32m====================================================================\033[0m"
echo -e "\033[1;37m TOKEN:\033[0m \033[1;33m${TOKEN}\033[0m"
echo -e "\033[1;37m URL LOCAL:\033[0m \033[1;36mhttp://localhost:${PORT}/lab?token=${TOKEN}\033[0m"
echo -e "\033[1;32m====================================================================\033[0m"
echo ""

exec uv run jupyter lab \
  --IdentityProvider.token="${TOKEN}" \
  --no-browser \
  --ip=0.0.0.0 \
  --port="${PORT}" \
  --allow-root
