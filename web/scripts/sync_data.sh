#!/usr/bin/env bash
# Copy pipeline outputs into the web app's static data folder.
set -euo pipefail
cd "$(dirname "$0")/../.."
mkdir -p web/public/data
slugs=()
for d in data/graph/*/; do
  slug=$(basename "$d")
  mkdir -p "web/public/data/$slug"
  cp "data/graph/$slug/graph.json" "web/public/data/$slug/"
  cp "data/processed/$slug/events.json" "web/public/data/$slug/"
  cp "data/insights/$slug/insights.json" "web/public/data/$slug/"
  slugs+=("\"$slug\"")
done
IFS=,; echo "[${slugs[*]}]" > web/public/data/index.json
echo "synced: ${slugs[*]}"
