#!/usr/bin/env bash
# Resolve a branch, tag or commit of an EdgeTX repository to a full commit SHA.
# Usage: resolve-ref.sh <owner/repo> <ref>
set -euo pipefail

repo=$1
ref=$2

if [[ $ref =~ ^[0-9a-f]{40}$ ]]; then
  echo "$ref"
  exit 0
fi

refs=$(git ls-remote "https://github.com/$repo" \
  "refs/tags/$ref^{}" "refs/tags/$ref" "refs/heads/$ref")

# prefer the commit a tag points at, then the tag, then a branch
for want in "refs/tags/$ref^{}" "refs/tags/$ref" "refs/heads/$ref"; do
  sha=$(awk -v w="$want" '$2 == w { print $1 }' <<< "$refs")
  if [ -n "$sha" ]; then
    echo "$sha"
    exit 0
  fi
done

echo "::error::Could not find '$ref' in $repo (use a branch, tag or full commit SHA)" >&2
exit 1
