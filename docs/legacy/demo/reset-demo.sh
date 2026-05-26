#!/bin/bash
# Reset plivo-python master + wipe mcp tools/ for a clean demo state.
set -e

# Truncate local trace first so this always runs even if a later step bails.
: > /tmp/prmcp-trace.jsonl
echo "trace cleared"

# Revert plivo-python calls.py to 560-line baseline
gh api 'repos/krishnarjunj-plivo/plivo-python/contents/plivo/resources/calls.py?ref=master' \
  --jq '.content' | base64 -d | head -560 > /tmp/calls_base.py
B64=$(base64 -i /tmp/calls_base.py | tr -d '\n')
SHA=$(gh api 'repos/krishnarjunj-plivo/plivo-python/contents/plivo/resources/calls.py?ref=master' --jq '.sha')
gh api -X PUT repos/krishnarjunj-plivo/plivo-python/contents/plivo/resources/calls.py \
  -f message=reset -f content="$B64" -f sha="$SHA" -f branch=master --jq '.commit.sha'

# Wait for any open PRs on mcp to merge (with stuck-PR rescue)
WAITED=0
until [ "$(gh pr list -R krishnarjunj-plivo/mcp --state open --json number --jq '. | length')" = "0" ]; do
  echo "waiting for open PRs to merge..."
  sleep 5
  WAITED=$((WAITED+5))
  if [ $WAITED -gt 20 ]; then
    STUCK=$(gh pr list -R krishnarjunj-plivo/mcp --state open --json number,mergeStateStatus --jq '.[] | select(.mergeStateStatus=="UNSTABLE") | .number')
    for n in $STUCK; do gh pr merge $n -R krishnarjunj-plivo/mcp --merge --delete-branch 2>/dev/null; done
    WAITED=0
  fi
done

# Wipe mcp tools/
for f in calls_diagnose.py calls_mine_blocks.py transcripts_create.py messages_archive.py; do
  S=$(gh api "repos/krishnarjunj-plivo/mcp/contents/tools/$f" --jq .sha 2>/dev/null)
  [ -n "$S" ] && gh api -X DELETE "repos/krishnarjunj-plivo/mcp/contents/tools/$f" \
    -f message=reset -f sha="$S" --jq '.commit.sha'
done

# Wait for the delete to propagate through GitHub's contents API. Without
# this, a dispatch fired immediately after reset can race the delete and
# PyGithub's create_file will see the file as still present (422 "sha wasn't
# supplied"). Poll the tree until tools/ is empty.
echo "waiting for delete propagation..."
for i in 1 2 3 4 5 6 7 8 9 10; do
  REMAINING=$(gh api 'repos/krishnarjunj-plivo/mcp/git/trees/main?recursive=true' \
    --jq '[.tree[] | select(.path | startswith("tools/")) | .path] | length' 2>/dev/null || echo "?")
  if [ "$REMAINING" = "0" ]; then
    echo "tools/ confirmed empty"
    break
  fi
  echo "  attempt $i: $REMAINING file(s) still visible, retrying..."
  sleep 2
done

echo "demo state clean"
