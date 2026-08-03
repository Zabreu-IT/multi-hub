#!/usr/bin/env bash
set -euo pipefail
base=${API_URL:-http://localhost:8080}/api/v1
curl -fsS -X POST "$base/products" -H 'Content-Type: application/json' ${API_KEY:+-H "X-API-Key: $API_KEY"} -d '{"name":"Tour de montaña","slug":"tour-de-montana","description":"Una salida guiada de día completo.","base_price":89,"currency":"USD","product_type":"tour","status":"active","images":[],"metadata":{}}'
echo
