#!/bin/sh
set -e

echo "Running idempotent seed (creates tables, seeds reference data)..."
i=1
until uv run python -m app.seed; do
  if [ "$i" -ge 5 ]; then
    echo "Seed failed after $i attempts, giving up." >&2
    exit 1
  fi
  echo "Seed attempt $i failed; retrying in 5s..."
  i=$((i + 1))
  sleep 5
done

echo "Starting uvicorn..."
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
