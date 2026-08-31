#!/usr/bin/env bash
# Aplica la migracion VINKO + Multi-Hub al Postgres de Multi-Hub (ash-micro-01).
# Uso: bash core/apply_vinko_migration.sh
# NO ejecutar contra prod sin aprobacion explicita de Vader.
set -euo pipefail

DB_CONTAINER="${DB_CONTAINER:-multi-hub-db-1}"
DB_USER="${DB_USER:-hub}"
DB_NAME="${DB_NAME:-multihub}"
MIGRATION_FILE="$(cd "$(dirname "$0")" && pwd)/migration_vinko.sql"

echo "[vinko-migration] contenedor: $DB_CONTAINER"
echo "[vinko-migration] archivo:    $MIGRATION_FILE"

docker cp "$MIGRATION_FILE" "$DB_CONTAINER":/tmp/migration_vinko.sql
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 -f /tmp/migration_vinko.sql

echo "[vinko-migration] verificacion:"
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -c \
  "SELECT 'organizer_tiers=' || count(*) FROM organizer_tiers UNION ALL SELECT 'countries=' || count(*) FROM countries;"
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -c \
  "SELECT column_name FROM information_schema.columns WHERE table_name='users' AND column_name IN ('role','tier_id','gmv_total','slug') ORDER BY 1;"
echo "[vinko-migration] OK"
