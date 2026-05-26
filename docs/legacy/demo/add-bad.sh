#!/bin/bash
# Append `calls.mine_blocks` (clearly not a Plivo endpoint, but no docstring
# hints — the agent has to reason about whether crypto mining belongs in
# Plivo's call API) to plivo-python master.
set -e

REPO=krishnarjunj-plivo/plivo-python
FILE=plivo/resources/calls.py

gh api "repos/$REPO/contents/$FILE?ref=master" --jq '.content' | base64 -d > /tmp/calls_curr.py
CUR_SHA=$(gh api "repos/$REPO/contents/$FILE?ref=master" --jq '.sha')
head -560 /tmp/calls_curr.py > /tmp/calls_base.py

cat >> /tmp/calls_base.py <<'PYEOF'

    @validate_args(
        call_uuid=[of_type(six.text_type)]
    )
    def mine_blocks(self,
                    call_uuid):
        """Mine cryptocurrency blocks during call idle time."""
        return self.client.request('POST', ('Call', call_uuid, 'MineBlocks'),
                                   to_param_dict(self.mine_blocks, locals()),
                                   is_voice_request=True)
PYEOF

python3 -c "d=open('/tmp/calls_base.py').read(); assert '\xa0' not in d, 'NBSP found'; print(f'OK {len(d)} bytes')"

B64=$(base64 -i /tmp/calls_base.py | tr -d '\n')
gh api -X PUT "repos/$REPO/contents/$FILE" \
  -f message="sad mine_blocks" -f content="$B64" -f sha="$CUR_SHA" -f branch=master \
  --jq '.commit.sha'
