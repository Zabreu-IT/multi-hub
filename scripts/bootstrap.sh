#!/usr/bin/env bash
set -euo pipefail
cp -n .env.example .env || true
docker compose -f infra/docker/docker-compose.yml up --build -d
echo "Multi-Hub: http://localhost:${PORT:-8080}"
