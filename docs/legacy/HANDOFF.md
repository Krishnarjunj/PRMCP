# Hackathon Handoff — read first on session restart

> Last refreshed: **2026-05-23 ~06:00** (demo day). Build phase wrapped 2026-05-22 Hr 15.5 (see lower sections — still authoritative for the pipeline). **Post-wrap work**: live pipeline visualizer + one-command launcher + auto-runner daemon (the "Demo-day extension" block below).
> Refresh this doc whenever new tooling lands or judges' visible surface changes.

## Demo-day extension — visualizer + one-command launcher (2026-05-23)

The demo now has **two visible surfaces**, not just the GH Actions run:

1. **`prmcp-up`** — a single command that boots everything for a teammate / fresh laptop:
   - Loads `.env` at repo root (see `.env.example` for required keys: `AZURE_OPENAI_API_KEY`, `PAT_TOKEN`).
   - Spawns Vite dev server in `viz/` (http://localhost:5173).
   - Spawns `prmcp.daemon` — watches `plivo-python-fork/plivo/resources/*.py`, polls mtimes every 2s, debounces 3s, then runs `prmcp.run`. New trace lines flow into `/tmp/prmcp-trace.jsonl` automatically.
   - Defaults to `PRMCP_DRY_RUN=1` so accidental boots don't push real PRs. Flip in `.env` for live mode.
   - Ctrl-C tears both down cleanly.

2. **`viz/`** — Vite + React + React Flow visualizer. Vertical 6-stage pipeline (trigger → diff_sdk → synth_tool → shadow_agent → open_pr → pr_opened). Left rail shows real runs (read from `/tmp/prmcp-trace.jsonl` via a Vite dev-server middleware) **above** four canonical demo runs. SSE pushes appended lines into the UI in ~200ms. Aesthetic is deep black + Plivo cobalt; Geist + Geist Mono; no purple, no shadow-2xl.

### Demo flow on the visualizer

1. `prmcp-up` running, browser at `localhost:5173`.
2. **Tier-1** (no creds needed): pythonl one-liner appends a fake trace record → new run lands in LIVE section within ~200ms via SSE.
3. **Tier-2** (real pipeline): add a method to a baseline-tracked resource in `plivo-python-fork/plivo/resources/*.py` (e.g. `calls.py`). Daemon log shows `detected change` → `trigger` → `new_pairs=1`; ~6s later trace line lands; visualizer's LIVE section shows the new run with all six stages green and a parsed dry-run preview card on the Open PR stage (with a `DRY RUN` pill, no external link). Real `pr_opened` runs (live mode) render a clickable PR card.

### Files added since the build wrap

- `prmcp/prmcp/daemon.py` — mtime poller + debounced trigger.
- `prmcp/prmcp/cli.py` — `prmcp-up` orchestrator (.env loader, viz + daemon spawn, signal handling).
- `prmcp/pyproject.toml` — `[project.scripts]` exposes `prmcp-up`, `prmcp-daemon`, `prmcp-run`.
- `.env.example` — required env-var template.
- `viz/` (entire tree) — Vite/React/TS app, mock + real run merge, Playwright screenshot loop in `scripts/screenshot.ts`.
- `viz/server/trace-api.ts` — Vite middleware: `GET /api/trace` (snapshot) + `GET /api/trace/stream` (SSE on `fs.watch`).

### Known sharp edges

- `prmcp-up` doesn't run `npm install` if `viz/node_modules` is present — but if it's missing it auto-runs install once. Just don't manually `rm -rf` it mid-demo.
- The Vite middleware reads the trace file uncached; if the file is truncated, the SSE listener resets and replays remaining lines (one-off re-render in the UI). Don't `> /tmp/prmcp-trace.jsonl` while demoing.
- The visualizer's bottom-left rail "TAILING · N LINES" turns green only when `/api/trace` returns successfully. If it stays gray, the Vite plugin didn't pick up `vite.config.ts` — restart `prmcp-up`.
- **Backend is unchanged** by all of the above. `prmcp/prmcp/run.py`, `_append_trace`, `_process_pair` etc. are exactly as they were at the build wrap. The visualizer only reads.

### To verify before demo

```sh
# Both processes alive
lsof -ti :5173 && pgrep -f prmcp.daemon

# Trace API serving
curl -s http://localhost:5173/api/trace | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'lines={d[\"lineCount\"]} runs={len(d[\"runs\"])}')"

# Backend tests still green
cd prmcp && .venv/bin/python -m pytest tests/ -x -q   # expect 42 passed
```

---



## Where we are

- **Time**: 2026-05-22, Hr 15.5 of 24. Segments 0-2, 2-5, 5-8, 8-12, 12-15, 15-18 all complete. **Build phase ended early** — remaining time goes to demo prep / buffer.
- **Source of truth**: `HANDOFF.md` (this file). `HARDENED.md` is the hour-by-hour plan but has accumulated stale references — cite HANDOFF first.
- **Track**: **PRMCP — locked**. Hr-4 canary PASSED. Doctor fallback dead.
- **HEAD**: `origin/main` carries the Hr 15-18 wrap (auto-merge hardening notes + final risks). 42/42 tests green under Python 3.11.15.

## ✅ Hr 15-18 COMPLETE — auto-merge live, pipeline end-to-end automated

The judges will see a workflow_dispatch on WATCHED that, with zero human-in-the-loop, opens a labeled PR on TARGET and auto-merges it.

- ✅ TARGET `.github/workflows/auto-merge.yml` live at `bcb4b06`. Triggers `pull_request: [opened, labeled, synchronize]`; gate: `contains(labels, 'agent-validated') && actor != 'github-actions[bot]'`. Hardened with `concurrency: auto-merge-${{ pr_number }}` (cancel-in-progress: false) + a `gh pr view --json state` pre-check that skips the merge step if the PR has already been merged by a prior queued run.
- ✅ TARGET `PAT_TOKEN` secret registered at 2026-05-22 16:21:20Z (same classic PAT as WATCHED, scopes: gist, read:org, repo, workflow).
- ✅ Smoke validation: dispatches `26299412612` and `26299655404` on WATCHED both produced PRs on TARGET that auto-merged.
  - PR #5 (pre-hardening): OPEN→MERGED **11s**. One run ✓ success, one ❌ failure with `Merge already in progress (mergePullRequest)` — the duplicate trigger race that motivated the hardening.
  - PR #6 (post-hardening): OPEN→MERGED **10s**. One run ✓ success (10s, did the merge), one ✓ skipped at job-level (label not present on the `opened` event payload). **No red ❌.**
- ✅ TARGET reset at commit `0778c4f` (deleted `tools/transcripts_create.py` via gh api). No open agent-validated PRs — next demo dispatch will open a clean PR #7.
- ⚠ Paired rehearsal skipped per team decision (B done). Acceptance was met by the two live smoke dispatches above; rehearsal would have been confirmation only.

### Demo-day dispatch (single command)

```bash
gh workflow run prmcp.yml -R krishnarjunj-plivo/plivo-python --ref master
# Watch end-to-end (auto-exits on completion):
gh run watch $(gh run list -R krishnarjunj-plivo/plivo-python --workflow prmcp.yml -L 1 --json databaseId --jq '.[0].databaseId') -R krishnarjunj-plivo/plivo-python --exit-status
# Then show the resulting PR (most recent on TARGET):
gh pr list -R krishnarjunj-plivo/mcp --label agent-validated --state all -L 1
```

Expected: WATCHED run completes in ~30-35s, then TARGET PR opens + auto-merges in ~10s. Total wall time ~45s from dispatch to merged PR.

## ✅ Hr 8-12 COMPLETE — pipeline E2E green

First end-to-end successful dispatch: run **`26294766320`** on WATCHED
produced **PR `krishnarjunj-plivo/mcp#2`** ("prmcp: add transcripts_create
(auto-synthesized)") with the `agent-validated` label. The
`prmcp-trace.jsonl` artifact contains the golden row:

```
{"ts": "2026-05-22T14:50:14Z", "resource": "transcripts", "py_name": "create",
 "tool_name": "transcripts_create", "verdict": "valid", "action": "pr_opened",
 "url_or_reason": "https://github.com/krishnarjunj-plivo/mcp/pull/2"}
```

### Root cause of the 401 streak (Hr 11–12)

NOT model-specific access control as the previous HANDOFF hypothesized.
The `AZURE_OPENAI_API_KEY` GH secret on `krishnarjunj-plivo/plivo-python`
was **stale** — the local-pasted key worked end-to-end, the registered
secret value did not. Diagnosed by a parallel Claude agent running a
4-probe auth survey (both `api-key` and `Authorization: Bearer` schemes
returned HTTP 200 locally; CI 401'd). Fix:
`gh secret set AZURE_OPENAI_API_KEY -R krishnarjunj-plivo/plivo-python`
re-registered to the current portal value. `gpt-5.4-mini` is the right
model and IS deployed on the resource — no `shadow_agent.py` change
needed in the end. Run IDs of the dead 401 dispatches (kept for forensic
reference): `26293033279`, `26293127887`, `26293406446`.

**Lesson for future Azure-in-CI failures**: probe
local-key-vs-registered-secret parity FIRST before suspecting model
access / IAM / endpoint. The GH secret list shows update timestamps —
compare against last known-good run.

## ⚠ Security note

The user **pasted the Azure OpenAI API key in chat plaintext** during the
Gemini → Azure swap. The key is now in the conversation transcript. The same
value was registered as the `AZURE_OPENAI_API_KEY` GH secret on WATCHED. Tell
the user to **rotate the key from the Azure portal post-hackathon** — the
secret on GH should also be updated when they do.

## Hr 8-12 deliverables (shipped)

Note: "Owner A" rows on the WATCHED repo land on `krishnarjunj-plivo/plivo-python:master`, not this repo's main. SHAs from both repos are intermixed below — each row is on whichever repo makes sense for the change.

| Step | Owner | Status | Commits |
|---|---|---|---|
| 1 | B | shadow_agent.py initial Gemini version | `1131aa5` |
| 2 | A | open_pr.py adds `agent-validated` label | `82b6c6c` |
| 3 | A | prmcp/run.py orchestrator | `dd76740` |
| 3a | A | run.py scope to baseline + `PRMCP_EXTRA_RESOURCES` | `c8d9489` |
| 4 | A | TARGET seed PR (`mcp` server.py trace hook) | MERGED `27459566` |
| 5 | A | prmcp.yml workflow on WATCHED master | `7821165` |
| 5a | A | PAT auth fix for private-repo pip install | `c33cc46` |
| 5b | A | env var: GEMINI → AZURE_OPENAI on WATCHED | `aea666d` |
| — | A | Pre-seed `transcripts.py` on WATCHED master | `0abcad1` |
| — | A | sdk_snapshot baseline moved inside prmcp package | `df43799` |
| — | A | Gemini 2.5 → 2.0 → 1.5 model attempts | `607fc0e`, `ee329d8` |
| — | A | Full rewrite shadow_agent → Azure OpenAI | `a8b3fad` |
| — | A | AzureOpenAI client variant (404'd, reverted) | `2cda1e1` |
| — | A | Back to OpenAI(base_url=v1) + dual auth headers | `aff045d` |

Hr 8-12 success criterion: "PR on TARGET with `agent-validated` label + trace
artifact uploaded" — **MET** via run `26294766320` and PR
`krishnarjunj-plivo/mcp#2`.

## Live E2E status (workflow dispatch results)

Most recent dispatch `26294766320` (post-secret-rotation):
- ✅ checkout, setup-python, install prmcp (with PAT auth via
  `git config --global url.insteadOf`)
- ✅ run orchestrator entered with `new_pairs=1` (transcripts/create)
- ✅ 429 inject demo beat fires correctly (warning + 1s sleep)
- ✅ AzureOpenAI `chat/completions` returned `verdict=valid` for
  `transcripts/create` (single-shot, no retries needed)
- ✅ trace JSONL written (1 line, `action=pr_opened`, URL to PR #2)
- ✅ open_pr.py opened PR #2 on `krishnarjunj-plivo/mcp` with
  `agent-validated` label
- ✅ upload-artifact succeeded
- Exit code 0

`prmcp-trace.jsonl` from run `26294766320` is the demo artifact judges will
see. PR #2 on `krishnarjunj-plivo/mcp` is the visible deliverable.

## Canonical decisions (LOCKED — do not re-litigate)

- **Fork owner**: `krishnarjunj-plivo` (Person A's GH).
  - WATCHED: `krishnarjunj-plivo/plivo-python` (default branch: `master`).
  - TARGET: `krishnarjunj-plivo/mcp` (default branch: `main`).
- **`prmcp/` install path**:
  ```
  pip install "prmcp @ git+https://github.com/plivo-hackathon-26/krishnarjun-tusshar-atomic-token.git@main#subdirectory=prmcp"
  ```
- **Cross-team JSON contract**: `contract_version = 1` with `client_attr`.
- **Baseline location**: `prmcp/prmcp/sdk_snapshot_2026-05-22.json` (inside
  the package; ships via pip thanks to `package-data` in pyproject).

## GitHub state (carries across devices)

Repo secrets on `krishnarjunj-plivo/plivo-python` (WATCHED):
- `PAT_TOKEN` — classic PAT, scopes `gist`, `read:org`, `repo`, `workflow`.
- `AZURE_OPENAI_API_KEY` — the one user pasted in chat; rotate post-hackathon.
- `GEMINI_API_KEY` — still registered but no longer referenced by the workflow.

Repo variable: `MCP_REPO=krishnarjunj-plivo/mcp`.

Workflow file: `.github/workflows/prmcp.yml` on WATCHED master. Triggers:
`pull_request: closed → master` + `workflow_dispatch`. Env includes
`PRMCP_INJECT_429=1`, `PRMCP_EXTRA_RESOURCES=transcripts`,
`PRMCP_TRACE_PATH=$GITHUB_WORKSPACE/prmcp-trace.jsonl`, `MCP_REPO=${{ vars.MCP_REPO }}`.

WATCHED has `plivo/resources/transcripts.py` + the `client.py` binding pushed
at `0abcad1` — produces exactly one new (resource, py_name) pair against
baseline; safe to leave there for the demo.

TARGET has the merged seed PR `27459566` adding `_trace` to `mcp.tool`
decorator. After any future tool invocation on TARGET, `$PRMCP_TRACE_PATH`
gets appended to with `{ts, tool, args, status}`.

## Local device state (per-machine)

- Python 3.11.15 at `/opt/homebrew/bin/python3.11`.
- Node v26 at `/opt/homebrew/bin/node`. `npx @modelcontextprotocol/inspector` cached.
- `prmcp/.venv/` — Python 3.11 venv with `prmcp` editable + pytest + openai SDK.
- `plivo-python-fork/` — extracted `plivo==4.60.1` wheel (PyPI).
- `/tmp/mcp-fork/` — local checkout of `krishnarjunj-plivo/mcp` (seed PR branch).
- `/tmp/plivo-watched/` — local checkout of `krishnarjunj-plivo/plivo-python`
  master with the workflow + transcripts.py pushed.

To regenerate the wheel extract on a fresh box:
```bash
/opt/homebrew/bin/python3.11 -m pip download plivo==4.60.1 --no-deps -d /tmp/plivo-pypi
mkdir -p plivo-python-fork && cd plivo-python-fork
/opt/homebrew/bin/python3.11 -m zipfile -e /tmp/plivo-pypi/plivo-4.60.1-*.whl .
```

## Hr 12-15 plan (completed)

Pipeline is green; switch from unblocking to polish + demo prep.

**Real Hr 12-15 priority order**:

1. ~~**WATCHED workflow gate hardening**~~ ✅ landed `b88e5df` on WATCHED master;
   verified by green dispatch `26295362203` under the strict gate.
2. ~~**429-inject visibility**~~ ✅ landed — `shadow_agent._maybe_inject_429`
   now `print(..., flush=True)`s the demo beat so it surfaces in CI logs
   regardless of logger level.
3. ~~**`shadow_agent` retry-with-backoff on transient 5xx**~~ ✅ landed —
   `_call_with_retries` wraps `_call_openai` with 2 retries + exponential
   backoff on `RateLimitError`/`InternalServerError`/`APIConnectionError`/
   `APITimeoutError`. 3 new pytest cases cover retry-then-succeed,
   retry-then-give-up, and non-retryable propagation.
4. ~~**Snake-case `_default_tool_name`**~~ ✅ landed — sub_resource entries
   now render as `accounts_subaccounts_get` /
   `regulatory_compliance_compliance_document_types_list` (was
   `accounts_Subaccounts_get`). Test added in
   `test_synth_tool_full_render.py`.
5. ~~**Demo script rehearsal**~~ ⚠ descoped — team called the build phase
   complete after Hr 15-18 smoke validated end-to-end automation. Single
   demo dispatch command captured in the "Demo-day dispatch" block above.

## How to resume in a new session

Build phase is wrapped. Demo day prep only from here on. After `/clear`, paste:

```
Resume demo prep on the PRMCP hackathon project at
/Users/krishnarjun.j/Krish/krishnarjun-tusshar-atomic-token.

Step 1: Read HANDOFF.md fully. Build phase is complete — Hr 0-18 all done,
auto-merge live on TARGET, smoke-validated end-to-end via PR #5+#6.
Paired rehearsal was descoped by the team.

Step 2: Run the Quick health check at the bottom of HANDOFF.md. Confirm:
  - atomic-token main HEAD has the Hr 15-18 wrap commit on top of 3c2fd53
  - WATCHED master HEAD = b88e5df (unchanged this segment)
  - TARGET main has auto-merge.yml at .github/workflows/ + PAT_TOKEN secret
  - pytest = 42/42 green
  - working tree clean

Step 3: One-command demo dispatch is captured in the "Demo-day dispatch"
block at the top of this file. Test it once before the live demo. After
the test run, reset TARGET (delete tools/transcripts_create.py via gh api)
so the actual demo opens a fresh PR.

Treat HANDOFF.md as the live state. Pushes to main / WATCHED master /
TARGET main still need explicit per-push OK each time.
```

## HARDENED stale refs (Hr 8-12 overrides)

- Install path: HARDENED L151 has placeholder. **Real**: see "Canonical decisions" above.
- TARGET repo: HARDENED §5/§8 say `plivo-hackathon-2026/mcp`. **Real**: `krishnarjunj-plivo/mcp`.
- Demo beat 2: HARDENED references `plivo-mcp-fork/server.py`. **Real**: `krishnarjunj-plivo/mcp/server.py`.
- PAT scopes: HARDENED L99 says `public_repo`. **Real**: `repo` + `workflow`.
- Hr-4 canary fallback row: HARDENED still describes Doctor switchover. **Real**: dead since Hr 4.
- google-genai pin: HARDENED L115 says `>=0.3.0`. **Real**: `openai>=1.50` now; google-genai dropped.
- shadow_agent provider: HARDENED §6 says Gemini-only. **Real**: Azure OpenAI via openai SDK (Gemini swapped out at Hr 11 due to 503/429/404 dead-ends).
- Baseline file location: any HARDENED reference to `prmcp/fixtures/sdk_snapshot...`. **Real**: `prmcp/prmcp/sdk_snapshot...` (moved at `df43799` so package-data ships it).

## Reality gaps (carry forward)

1. **`plivo==4.60.1` exists on PyPI but NOT on `github.com/plivo/plivo-python`** (highest tag is `v4.59.5`). Use wheel extract (snippet above). `plivo-python-fork/` is in `.gitignore`.
2. **No public Plivo OpenAPI spec.** AST-parse `plivo-python-fork/` instead — `diff_sdk.py` does this.
3. **WATCHED master has shape-undetectable resources** (`conferences`, `phlos`). `run.py` sidesteps by walking only baseline source-stems + extras.
4. **Azure resource exposes only `/openai/v1/`** (Foundry-style), not standard `/openai/deployments/<name>/...`. Standard path 404s on this resource.

## Hard rules (carry forward)

1. **Commit + push every ~30 min.** Both devs.
2. **Do NOT touch upstream `plivo/*`** — `open_pr.py` guardrail refuses.
3. **If HARDENED.md and reality contradict, flag before improvising.** Running list above.
4. **No `/clear` mid-segment.** Fine at segment boundaries (Hr 8, Hr 12, …). Refresh this doc first.
5. **Hackathon-mode push policy**: pushing to `main` (and direct pushes to WATCHED `master`) require explicit per-push OK in the Claude session.

## Open risks carrying into Hr 15-18

- **Leaked Azure key.** Pasted in chat transcript twice (Hr 11 swap + Hr 12.5
  re-register). The current GH secret matches the leaked value. Rotate
  post-hackathon from the Azure portal and run
  `gh secret set AZURE_OPENAI_API_KEY -R krishnarjunj-plivo/plivo-python` with
  the new value.
- **Single-resource demo surface.** Today the pipeline only walks
  `transcripts/create` (the seeded pair). If we want a second resource for
  the demo, push another resource to WATCHED master and add it to
  `PRMCP_EXTRA_RESOURCES` in `prmcp.yml`. Run 26294766320 is the only live
  OpenAI sample we have — `_extract_verdict` parsing has not been
  re-exercised against a different schema shape.
- **TARGET PR drift during rehearsal.** Each pipeline dispatch opens a new
  PR with a unique timestamp branch. Close + delete-branch before each
  rehearsal so the demo opens a clean fresh PR. Bulk close pattern:
  `gh pr list -R krishnarjunj-plivo/mcp --label agent-validated --state open --json number --jq '.[].number' | xargs -I{} gh pr close {} -R krishnarjunj-plivo/mcp --delete-branch`.
- ~~**Auto-merge loop on TARGET (Hr 15-18 work-item).**~~ ✅ resolved in
  `bcb4b06`. Job-level `if:` includes `github.actor != 'github-actions[bot]'`;
  no observed loop in smoke runs `26299412612` / `26299655404`. Concurrency
  group + skip-if-merged pre-check also prevent a different failure mode
  (duplicate `opened`+`labeled` triggers racing on the same PR).

## Background docs (gitignored, on disk both devices)

- `HARDENED.md` — hour-by-hour plan. Stale in places; cite HANDOFF first.
- `PRMCP.md` — narrative deep-dive on architecture.
- `PLAN.md` — original ideation; Idea B (Doctor) is the dead fallback.
- `Context.md` — raw Slack export of hackathon channel.

## Quick health check (run on session start)

```bash
cd /Users/krishnarjun.j/Krish/krishnarjun-tusshar-atomic-token
git fetch origin && git status                # should show clean tree + main up-to-date
git log --oneline -7                          # top is the Hr 15-18 wrap commit, then 3c2fd53, 09fa81c, 13ec91e, c944259, 63b4808, d880ee3
prmcp/.venv/bin/python -m pytest prmcp/tests/ # 42/42 green
ls plivo-python-fork/plivo/resources/ | wc -l # 33
gh secret list -R krishnarjunj-plivo/plivo-python | grep AZURE  # AZURE_OPENAI_API_KEY present, updated ~14:49Z+
gh secret list -R krishnarjunj-plivo/mcp | grep PAT  # PAT_TOKEN present, updated 2026-05-22 16:21Z
gh api repos/krishnarjunj-plivo/plivo-python/commits/master --jq '.sha' # b88e5df... (strict gate)
gh api repos/krishnarjunj-plivo/mcp/commits/main --jq '.sha'            # 0778c4f... or later (auto-merge live)
gh pr list -R krishnarjunj-plivo/mcp --label agent-validated --state open -L 5  # empty (clean for next dispatch)
```

If any of these fail, **do NOT run the demo dispatch** — figure out what regressed first.
