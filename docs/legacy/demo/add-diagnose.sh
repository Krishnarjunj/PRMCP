#!/bin/bash
# Append `calls.diagnose` to plivo-python master via gh api (no NBSP risk).
set -e

REPO=krishnarjunj-plivo/plivo-python
FILE=plivo/resources/calls.py

# Fetch current
gh api "repos/$REPO/contents/$FILE?ref=master" --jq '.content' | base64 -d > /tmp/calls_curr.py
CUR_SHA=$(gh api "repos/$REPO/contents/$FILE?ref=master" --jq '.sha')

# Strip any previous demo additions (anything past line 560)
head -560 /tmp/calls_curr.py > /tmp/calls_base.py

# Append the diagnose method with guaranteed ASCII spaces
cat >> /tmp/calls_base.py <<'PYEOF'

    @validate_args(
        call_uuid=[of_type(six.text_type)]
    )
    def diagnose(self,
                 call_uuid):
        """Run a network diagnostic on the call leg."""
        return self.client.request('POST', ('Call', call_uuid, 'Diagnose'),
                                   to_param_dict(self.diagnose, locals()),
                                   is_voice_request=True)
PYEOF

# Sanity: must be zero NBSP
python3 -c "d=open('/tmp/calls_base.py').read(); assert '\xa0' not in d, 'NBSP found'; print(f'OK {len(d)} bytes, {d.count(chr(10))} lines')"

# Push
B64=$(base64 -i /tmp/calls_base.py | tr -d '\n')
gh api -X PUT "repos/$REPO/contents/$FILE" \
  -f message="happy diagnose" -f content="$B64" -f sha="$CUR_SHA" -f branch=master \
  --jq '.commit.sha'
