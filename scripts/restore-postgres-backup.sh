#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-$HOME/cv-automation-workflow}"
cd "$APP_DIR"

env_value() {
  awk -F= -v key="$1" '$1 == key {sub(/^[^=]*=/, ""); print; exit}' .env
}

POSTGRES_USER="$(env_value POSTGRES_USER)"
POSTGRES_DB="$(env_value POSTGRES_DB)"
BACKUP_S3_BUCKET="$(env_value BACKUP_S3_BUCKET)"
BACKUP_S3_PREFIX="$(env_value BACKUP_S3_PREFIX)"
: "${POSTGRES_USER:=postgres}"
: "${POSTGRES_DB:=cv_db}"
: "${BACKUP_S3_BUCKET:?BACKUP_S3_BUCKET is required in .env}"
BACKUP_S3_PREFIX="${BACKUP_S3_PREFIX:-postgres}"
DOCKER="${DOCKER:-docker}"

db_id="$($DOCKER compose ps -q db)"
if [ -z "$db_id" ]; then
  echo "PostgreSQL container is not running" >&2
  exit 1
fi

has_schema="$($DOCKER compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT to_regclass('public.alembic_version') IS NOT NULL")"
if [ "$has_schema" = "t" ]; then
  echo "PostgreSQL already has an application schema; skipping restore."
  exit 0
fi

latest_uri="s3://${BACKUP_S3_BUCKET}/${BACKUP_S3_PREFIX}/latest.dump"
tmp_file="$(mktemp)"
trap 'rm -f "$tmp_file"' EXIT

if ! aws s3 cp "$latest_uri" "$tmp_file" --only-show-errors; then
  echo "No PostgreSQL backup found at ${latest_uri}; continuing with an empty database."
  exit 0
fi

echo "Restoring PostgreSQL backup from ${latest_uri}..."
cat "$tmp_file" | $DOCKER compose exec -T db pg_restore \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  --clean \
  --if-exists \
  --no-owner \
  --no-acl

echo "PostgreSQL restore complete."