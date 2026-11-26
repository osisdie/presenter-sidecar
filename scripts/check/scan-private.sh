#!/usr/bin/env bash
# Scan tracked (+ staged) files for private terms.
#
# Pattern sources (one extended regex per line, '#' comments allowed, case-insensitive):
#   1. scripts/check/generic-denylist.txt  committed; generic leaks such as absolute user paths
#   2. .private-denylist                    local and gitignored; your own names, IDs, paths
#   3. $PRIVATE_DENYLIST                    optional env var (e.g. a CI secret), newline-separated
#
# Usage: scripts/check/scan-private.sh [--all]   (--all also scans untracked, non-ignored files)
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
GENERIC=scripts/check/generic-denylist.txt
LOCAL=.private-denylist
PATTERNS=$(mktemp)
trap 'rm -f "$PATTERNS"' EXIT

for f in "$GENERIC" "$LOCAL"; do
  [ -f "$f" ] && grep -vE '^\s*(#|$)' "$f" >> "$PATTERNS" || true
done
if [ -n "${PRIVATE_DENYLIST:-}" ]; then
  printf '%s\n' "$PRIVATE_DENYLIST" | grep -vE '^\s*(#|$)' >> "$PATTERNS" || true
fi
[ -f "$LOCAL" ] || [ -n "${PRIVATE_DENYLIST:-}" ] || \
  echo "note: no $LOCAL (and no PRIVATE_DENYLIST); only generic patterns are checked" >&2
if [ ! -s "$PATTERNS" ]; then
  echo "no patterns to check"
  exit 0
fi

if [ "${1:-}" = "--all" ]; then
  FILES=$(git ls-files --cached --others --exclude-standard)
else
  FILES=$(git ls-files --cached)
fi
# The pattern list itself is allowed to contain the patterns.
FILES=$(printf '%s\n' "$FILES" | grep -vxF "$GENERIC" || true)
[ -z "$FILES" ] && { echo "nothing to scan"; exit 0; }

HITS=0
# Contents
if printf '%s\n' "$FILES" | tr '\n' '\0' | xargs -0 grep -nIiE -f "$PATTERNS" -- 2>/dev/null; then
  HITS=1
fi
# File names
if printf '%s\n' "$FILES" | grep -iE -f "$PATTERNS"; then
  HITS=1
fi
if [ "$HITS" -ne 0 ]; then
  echo "✗ private terms found (see above)" >&2
  exit 1
fi
echo "✓ no private terms found in $(printf '%s\n' "$FILES" | wc -l | tr -d ' ') files ($(wc -l < "$PATTERNS" | tr -d ' ') patterns)"
