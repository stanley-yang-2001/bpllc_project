#!/bin/sh
# Fails if web/openapi.json or web/src/api/schema.d.ts is out of date with the FastAPI app.
set -e
root=$(cd "$(dirname "$0")/.." && pwd)
tmp=$(mktemp -d)
python3 "$root/api/scripts/dump_openapi.py" "$tmp/openapi.json" >/dev/null
(cd "$root/web" && npx --no-install openapi-typescript "$tmp/openapi.json" -o "$tmp/schema.d.ts" >/dev/null)
diff -q "$tmp/openapi.json" "$root/web/openapi.json" >/dev/null || { echo "web/openapi.json is stale: run 'make gen-api'"; exit 1; }
diff -q "$tmp/schema.d.ts" "$root/web/src/api/schema.d.ts" >/dev/null || { echo "web/src/api/schema.d.ts is stale: run 'make gen-api'"; exit 1; }
echo "API types are up to date"
