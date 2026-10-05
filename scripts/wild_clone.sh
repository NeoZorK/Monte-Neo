#!/usr/bin/env bash
# Shallow-clone the repositories listed in a file (one owner/name per line) into a directory, for scripts/wild_scan.py.
#
#   gh search repos "freqtrade strategy" --language python --limit 100 --json fullName -q '.[].fullName' > repos.txt
#   scripts/wild_clone.sh repos.txt ~/wild
#
# Only public repositories; nothing is modified or pushed. Respect each repository's licence when you keep or share anything.
set -euo pipefail
if [ "$#" -ne 2 ]; then
  echo "usage: $0 <repos.txt> <target-dir>" >&2
  exit 2
fi
mkdir -p "$2"
while IFS= read -r repo; do
  [ -z "$repo" ] && continue
  dir="$2/$(echo "$repo" | tr '/' '_')"
  if [ -d "$dir" ]; then echo "skip $repo (already cloned)"; continue; fi
  git clone --depth 1 --quiet "https://github.com/$repo.git" "$dir" 2> /dev/null && echo "ok   $repo" || echo "FAIL $repo"
done < "$1"
