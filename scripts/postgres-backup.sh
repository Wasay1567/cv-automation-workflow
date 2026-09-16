#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-$HOME/cv-automation-workflow}"
cd "$APP_DIR"

if [ ! -f .env ]; then
  echo "Missing $APP_DIR/.env" >&2
  exit 1
fi

env_value() {
  awk -F= -v key="$1" '$1 == key {sub(/^[^=]*=/, ""); print; exit}' .env
}

POSTGRES_USER="$(env_value POSTGRES_USER)"
POSTGRES_DB="$(env_value POSTGRES_DB)"
BACKUP_S3_BUCKET="$(env_value BACKUP_S3_BUCKET)"
BACKUP_S3_PREFIX="$(env_value BACKUP_S3_PREFIX)"
AWS_ACCESS_KEY_ID="$(env_value AWS_ACCESS_KEY_ID)"
AWS_SECRET_ACCESS_KEY="$(env_value AWS_SECRET_ACCESS_KEY)"
AWS_REGION="$(env_value AWS_REGION)"
: "${POSTGRES_USER:=postgres}"
: "${POSTGRES_DB:=cv_db}"
: "${BACKUP_S3_BUCKET:?BACKUP_S3_BUCKET is required in .env}"
BACKUP_S3_PREFIX="${BACKUP_S3_PREFIX:-postgres}"

if [ -n "$AWS_ACCESS_KEY_ID" ] && [ -n "$AWS_SECRET_ACCESS_KEY" ]; then
  export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY
fi
if [ -n "$AWS_REGION" ]; then
  export AWS_REGION AWS_DEFAULT_REGION="$AWS_REGION"
fi

DOCKER="${DOCKER:-docker}"
if ! $DOCKER info >/dev/null 2>&1 && sudo docker info >/dev/null 2>&1; then
  DOCKER="sudo docker"
fi

latest_key="${BACKUP_S3_PREFIX}/latest.dump"
latest_uri="s3://${BACKUP_S3_BUCKET}/${latest_key}"
tmp_file="$(mktemp)"
trap 'rm -f "$tmp_file"' EXIT

echo "Creating PostgreSQL backup..."
$DOCKER compose exec -T db pg_dump \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  --format=custom \
  --no-owner \
  --no-acl \
  > "$tmp_file"

aws s3 cp "$tmp_file" "$latest_uri" --only-show-errors

# Keep exactly one object in this dedicated backup prefix.
aws s3api list-objects-v2 \
  --bucket "$BACKUP_S3_BUCKET" \
  --prefix "${BACKUP_S3_PREFIX}/" \
  --query 'Contents[].Key' \
  --output text \
  | tr '\t' '\n' \
  | while IFS= read -r key; do
      if [ -n "$key" ] && [ "$key" != "$latest_key" ]; then
        aws s3 rm "s3://${BACKUP_S3_BUCKET}/${key}" --only-show-errors
      fi
    done

echo "Backup uploaded to ${latest_uri}"