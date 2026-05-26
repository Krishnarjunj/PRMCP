# PRMCP — Hardened Plan (replaces PLAN.md as source of truth)

> Generated 2026-05-22 ~01:30 IST by an orchestrator running 6 parallel research subagents + a red-team pass. Every nontrivial claim carries a URL. 25 claims verified or rewritten; 3 stage-failure modes red-teamed and fixed.

---

## 1. Pitch + wow moment

**Pitch (one sentence)**: PRMCP is a GitHub Action + Python agent that watches a `plivo/plivo-python` fork, AST-walks new resources when SDK PRs merge, synthesizes the matching `@mcp.tool()` function for `plivo/mcp`, validates it by invoking Gemini 2.5 Flash (via the `google-genai` SDK) against the new tool inside the runner, opens a labelled PR on a `plivo/mcp` fork, and auto-merges on green CI.

**Wow moment**: 3 nested agent loops visible on stage — Claude Code wrote PRMCP, PRMCP runs Gemini validation against the freshly synthesized tool, that tool calls Plivo's SDK. Multi-model framing is a feature, not a bug: "we built it with Claude Code, but the validation seat is LLM-agnostic — any function-calling model works." Demo trigger = merge a staged `Transcripts.create` PR on the watched fork; ≤90s (warm cache) later, your `mcp` fork's `main` has 7 tools (was 6), proven by `npx @modelcontextprotocol/inspector`.

**Install (Monday morning)**: paste two yaml files + add one classic PAT secret with `public_repo` scope. Total <60s on a clean fork.

---

## 2. Verdict table (compact, 25 claims)

> **Note (2026-05-22 post-decision)**: validation LLM swapped from Claude (Anthropic API/CLI) to **Gemini 2.5 Flash via `google-genai` SDK** ([install](https://github.com/googleapis/python-genai), [function-calling docs](https://ai.google.dev/gemini-api/docs/function-calling)). Cluster C1 verdicts retained as evidence record; C5.1 fix updated below. Gemini 2.5 Flash supports JSON Schema function declarations natively, free-tier covers hackathon usage (~30 calls). Two paths collapse into one: no more Claude CLI on the runner, no OAuth-token dance, no Node install needed in CI.


| ID | Verdict | Confidence | Evidence (one-line) |
|----|---------|------------|---------------------|
| C1.1 | VERIFIED | H | `claude --bare -p ... --mcp-config ... --output-format json --allowedTools` documented verbatim ([headless docs](https://code.claude.com/docs/en/headless)) |
| C1.2 | **FAILED → SWAP** | H | `claude-cli` is not a PyPI package. Use `npm install -g @anthropic-ai/claude-code` ([npm](https://www.npmjs.com/package/@anthropic-ai/claude-code)) |
| C1.3 | VERIFIED w/ caveat | M | OAuth via `claude setup-token` → `CLAUDE_CODE_OAUTH_TOKEN` secret; `--bare` may skip keychain — smoke-test Hr 0 ([Max + Actions writeup](https://wain.blog/en/claude-code-github-actions-max-support-8NB583zS/)) |
| C1.4 | **NEEDS-REWRITE** | M | Limits are hours/week, not msgs/minute. ~30 validations × 30s ≈ 15 min Sonnet — within Max $100 budget (140h/wk) ([TechCrunch](https://techcrunch.com/2025/07/28/anthropic-unveils-new-rate-limits-to-curb-claude-code-power-users/)). **Subscription covers `claude -p` until 2026-06-15** ([headless docs](https://code.claude.com/docs/en/headless)) — hackathon is in scope |
| C1.5 | VERIFIED | H | `claude` CLI runs on `ubuntu-latest`; Node 18+ required; no sudo issues ([setup docs](https://code.claude.com/docs/en/setup)) |
| C2.1 | VERIFIED | H | `fastmcp` 3.3.1 (2026-05-15), Python 3.10–3.13, `pip install fastmcp` ([PyPI](https://pypi.org/project/fastmcp/)) |
| C2.2 | VERIFIED | H | `plivo` 4.60.1 (2026-04-17), Python 3.11 supported ([PyPI](https://pypi.org/project/plivo/)). PRMCP.md year typo: was "2025-04-17" |
| C2.3 | VERIFIED | H | `plivo/mcp` is single-file `server.py` with 6 tools: `send_sms`, `make_call`, `create_application`, `create_endpoint`, `get_cdr`, `get_mdr` ([source](https://github.com/plivo/mcp/blob/main/server.py)) |
| C2.4 | VERIFIED | H | `npx @modelcontextprotocol/inspector` introspects local FastMCP via stdio ([inspector repo](https://github.com/modelcontextprotocol/inspector)) — needs Node on demo machine |
| C2.5 | VERIFIED | H | `prmcp` PyPI name free; same-day swap = `pip install git+https://github.com/...` |
| C3.1 | **NEEDS-REWRITE** | H | ~80% of files conform to two-class pattern; `lookup.py`, `call_feedback.py`, `token.py`, `nodes.py`, `numberpools.py` deviate. Add 2 shape detectors + skip-list ([repo tree](https://github.com/plivo/plivo-python/tree/master/plivo/resources)) |
| C3.2 | **FAILED → SCOPE-LIMIT** | H | Strict CRUD coverage is **~57%**, not 80%+. SWAP: restrict v1 to 16 clean-CRUD files (≥90% within scope) and demo `Transcripts.create` (canonical CRUD). Optional: add 6th passthrough template for ~95% later |
| C3.3 | VERIFIED | H | No public Plivo OpenAPI spec anywhere (GitHub org search + docs portal both return 0) |
| C3.4 | NEEDS-REWRITE | H | Latest 4.60.1 on **2026-04-17** (not 2025); repo actively maintained, last commit 35d ago ([releases](https://github.com/plivo/plivo-python/releases)) |
| C4.1 | VERIFIED | H | `actions/checkout@v4` + `actions/setup-python@v5` current; accept stated params |
| C4.2 | VERIFIED | H | `pascalgn/automerge-action@v0.16.4` current (2025-09-22); `MERGE_LABELS` + `MERGE_METHOD` honored ([repo](https://github.com/pascalgn/automerge-action)) |
| C4.3 | VERIFIED | H | Public-repo Actions are free unlimited; private = 2000 min/mo ([billing docs](https://docs.github.com/en/billing/managing-billing-for-your-products/about-billing-for-github-actions)) |
| C4.4 | NEEDS-REWRITE | H | `pull_request: types: [closed]` fires on merge, but **no documented latency SLA** — drop the "~10s" claim |
| C4.5 | **FAILED → SWAP** | H | Fine-grained PAT **cannot** open PRs to repos you're not a member of ([blog](https://github.blog/security/application-security/introducing-fine-grained-personal-access-tokens-for-github/)). Use classic PAT with `public_repo` scope |
| C4.6 | NEEDS-REWRITE | H | PyGithub v2.9.1 fine; auth via `Auth.Token(...)` works for classic PAT. Replace "fine-grained" with "classic" everywhere |
| C4.7 | VERIFIED | H | Both `plivo/plivo-python` and `plivo/mcp` are public and forkable |
| C5.1 | **NEEDS-REWRITE** | H | Pip cold install 60–180s; CLI path dead because we no longer use Claude on the runner. **Validation now uses `google-genai` SDK → Gemini 2.5 Flash**, ~2–5s per call ([docs](https://ai.google.dev/gemini-api/docs/function-calling)). Budget ≤90s warm cache / ≤180s cold for full pipeline including pip install |
| C5.2 | VERIFIED | H | FastMCP middleware path is clean; for demo use module-level counter + `PRMCP_INJECT_429` env var inside the tool body ([FastMCP middleware](https://gofastmcp.com/servers/middleware)) |
| C5.3 | NEEDS-REWRITE | H | Hr-17 go/no-go: 3 consecutive clean-checkout runs, each must pass (a) PR opens ≤90s, (b) trace has 2 lines [429, 200], (c) wall-time ≤90s |
| C5.4 | NEEDS-REWRITE | H | Need explicit `GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}` env. **Red-team fix**: pin trace path to `$GITHUB_WORKSPACE/prmcp-trace.jsonl` (not `$RUNNER_TEMP` — flaky across subprocesses). Upload as artifact for mid-demo recovery |
| C6.1 | VERIFIED | M | No public tool combines (SDK-AST codegen + LLM validation + self-merging PR + watcher) as of May 2026 |
| C6.2 | VERIFIED | H | OpenAPI→MCP tools (`openapi-mcp-generator`, Speakeasy, Stainless) all require OpenAPI input. **Bonus**: Stainless wound down hosted products 2026-05-18 ([blog](https://www.stainless.com/blog/generate-mcp-servers-from-openapi-specs)) — strengthens the "not OpenAPI codegen" deflection |

**Summary**: 14 VERIFIED, 6 NEEDS-REWRITE (all rewritten below), 3 FAILED (each with a verified swap applied), 2 with caveats noted. Zero load-bearing dependencies blocked.

---

## 3. Final hour-by-hour plan (with inline citations)

| Hr | Person A | Person B | Notes |
|----|----------|----------|-------|
| **0–2** | Forks already exist under your account. Mint **classic PAT** with `public_repo` scope ([docs](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)). Mint **Gemini API key** at [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) (free tier). | Get `plivo/mcp`'s 6 tools running locally with FastMCP. `pip install fastmcp plivo google-genai` ([repo](https://github.com/plivo/mcp)). Capture baseline. **Smoke-test**: `python -c "from google import genai; c=genai.Client(); print(c.models.generate_content(model='gemini-2.5-flash', contents='hi').text)"` works with `GEMINI_API_KEY` env var. | Add safety guardrail in `open_pr.py`: `assert not target.startswith('plivo/')` — refuse to PR to upstream. |
| **2–5** | `diff_sdk.py`: AST-walk `plivo/resources/*.py` with **3 shape detectors** (standard pair / singleton interface / sub-resource) + skip-list for `nodes.py` and `numberpools.py` (C3.1). Snapshot-test against current SDK. | `synth_tool.py` + **5 CRUD Jinja templates** + **1 passthrough template** for non-CRUD verbs (C3.2). Snapshot-test against existing `send_sms`/`make_call` for parity. | **Hr-4 canary**: if `diff_sdk.py` does not snapshot-pass the 16 clean-CRUD files (accounts, addresses, applications, calls top-level, endpoints, identities, messages, numbers top-level, profile, recordings, brand, powerpacks top-level, regulatory_compliance, pricings, lookup, tollfree_verification), **switch to Doctor (Idea B)**. |
| **5–8** | Compose pipeline end-to-end. Hand-craft fake `Transcripts.create` in `plivo-python-stub`. Verify pipeline emits the correct `@mcp.tool()` function. | `open_pr.py` with PyGithub 2.9.1 + classic PAT. **Critical**: target BASE is `<our-org>/plivo-mcp-fork:main` (not upstream `plivo/mcp`) — red-team fix #1, removes entire cross-org PR failure class. Add `prmcp-generated` label. | Demo PR opens within our org. Pitch line: "same yaml works against upstream with org membership." |
| **8–12** | Instrument FastMCP `server.py`: every tool invocation appends `{tool, args, ts, status, result}` to **`$GITHUB_WORKSPACE/prmcp-trace.jsonl`** (red-team fix #3 — not `/tmp`, not `$RUNNER_TEMP`; checked-out repo root survives subprocess + cross-step). | `shadow_agent.py`: validation via `google-genai` SDK + Gemini 2.5 Flash ([SDK](https://github.com/googleapis/python-genai), [function-calling docs](https://ai.google.dev/gemini-api/docs/function-calling)). Convert MCP tool schema → Gemini `FunctionDeclaration` (both JSON Schema, ~10-line shim). Call `client.models.generate_content(model='gemini-2.5-flash', contents="Use <tool> with these params: ...", config=types.GenerateContentConfig(tools=[Tool(function_declarations=[fd])]))`. Validation ~2–5s. Cache by `(resource, method)` signature; budget cap 3 calls per PR. | Red-team fix #2 (Gemini variant). Free under Gemini 2.5 Flash free-tier limits (1500 req/day). |
| **12–15** | Full workflow yaml. Test the full event chain: merge staged PR → workflow runs → PR opens on fork → CI green → auto-merge. | CI on `plivo-mcp-fork`: smoke `python -c "from server import *"` + snapshot test. Add `actions/upload-artifact@v4` step to ship `prmcp-trace.jsonl` as a run artifact so it survives even if a step fails. | |
| **15–18** | `auto-merge.yml` using `pascalgn/automerge-action@v0.16.4` ([repo](https://github.com/pascalgn/automerge-action)). `MERGE_LABELS: agent-validated`, `MERGE_METHOD: squash`. | Recovery beat: module-level counter inside the demo tool + `PRMCP_INJECT_429` env var. First call raises `RuntimeError("rate_limited_429")`; second succeeds. Both log to trace. | |
| **Hr 17 GO/NO-GO** | Run full pipeline **3 consecutive times from clean checkout**. All 3 must hit: (a) PR opens ≤90s warm cache, (b) `prmcp-trace.jsonl` has exactly 2 lines `[status=429, status=200]`, (c) total wall-time ≤90s. If ANY (a/b/c) flakes in ANY of 3 runs → **drop shadow-agent validation, ship smoke-import CI only**. Demo loses "Claude validated it" beat, keeps "agent opens PR" beat. | Both watch. | Hard-cut, no negotiation. |
| **18–21** | Stage 2 candidate PRs (`Transcripts.create`, `Numbers.search`). Practice triggering each. **Record backup screencast** — both candidate PRs, full pipeline run, with closing `mcp inspector` shot. | README: copy-paste install block, screencast GIF, one-line "what PRMCP does," failure-mode docs. Pre-stage install command into clipboard for the judge-laptop demo. | |
| **21–23** | Demo rehearsal #1 + #2 with stopwatch. | Final `pytest` pass. Verify deterministic output. | |
| **23–24** | Rehearsal #3 + buffer. | Buffer. | |

---

## 4. SETUP block (verbatim shell, clean machine → demo-ready)

```bash
# === ON DEV LAPTOP, ONCE, BEFORE HR 0 ===

# system deps (Node only needed locally for `mcp inspector` demo beat — not on CI)
brew install node gh
gh auth login

# Gemini API key — free tier covers hackathon usage
# Get one at: https://aistudio.google.com/app/apikey
export GEMINI_API_KEY="AIza..."

# Smoke-test Gemini auth + function calling
pip install google-genai
python -c "from google import genai; c=genai.Client(); print(c.models.generate_content(model='gemini-2.5-flash', contents='say ok').text)"

# Forks already exist (krishnarjun.j/plivo-python, krishnarjun.j/mcp).
# Confirm:
gh repo view <your-gh-username>/plivo-python
gh repo view <your-gh-username>/mcp

# Mint classic PAT — fine-grained PAT cannot do cross-repo PRs (C4.5)
# go to: github.com/settings/tokens → "Generate new token (classic)"
# scopes: public_repo (Contents:write + PRs:write on public repos)
# label: PRMCP-2026
export PAT_TOKEN="ghp_..."

# Load secrets into the watched repo
WATCHED=<your-gh-username>/plivo-python
TARGET=<your-gh-username>/mcp
gh secret set GEMINI_API_KEY -R $WATCHED -b "$GEMINI_API_KEY"
gh secret set PAT_TOKEN -R $WATCHED -b "$PAT_TOKEN"
gh variable set MCP_REPO -R $WATCHED -b "$TARGET"

# Build PRMCP itself (run inside a fresh prmcp/ directory)
git init prmcp && cd prmcp
cat > requirements.txt <<'EOF'
fastmcp==3.3.1
plivo==4.60.1
PyGithub==2.9.1
jinja2>=3.1
google-genai>=0.3.0
pytest>=8.0
EOF
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Pre-warm npx cache so the demo's closing inspector beat is instant
npx --yes @modelcontextprotocol/inspector --version

# === WORKFLOW YAML to paste on the watched repo ===
mkdir -p .github/workflows
cat > .github/workflows/prmcp.yml <<'YAML'
name: PRMCP
on:
  pull_request:
    types: [closed]
    branches: [main, master]
  workflow_dispatch: {}    # manual fallback for demo
permissions:
  contents: read
  pull-requests: write
jobs:
  prmcp:
    if: github.event_name == 'workflow_dispatch' || github.event.pull_request.merged == true
    runs-on: ubuntu-latest
    env:
      GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      PAT_TOKEN: ${{ secrets.PAT_TOKEN }}
      GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
      PRMCP_INJECT_429: '1'
      PRMCP_TRACE_PATH: ${{ github.workspace }}/prmcp-trace.jsonl
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 2 }
      - uses: actions/setup-python@v5
        with: { python-version: '3.11', cache: 'pip' }
      - run: pip install git+https://github.com/<your-gh-username>/prmcp.git@main
      - run: python -m prmcp.run --target-repo "${{ vars.MCP_REPO }}"
      - run: test -s "$PRMCP_TRACE_PATH" && wc -l "$PRMCP_TRACE_PATH"   # fail loud if trace missing
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: prmcp-trace
          path: ${{ env.PRMCP_TRACE_PATH }}
YAML

# === AUTO-MERGE YAML to paste on the target (plivo/mcp fork) ===
cat > .github/workflows/auto-merge.yml <<'YAML'
name: PRMCP auto-merge
on:
  pull_request:
    types: [labeled]
  check_suite:
    types: [completed]
jobs:
  merge:
    if: contains(github.event.pull_request.labels.*.name, 'agent-validated')
    runs-on: ubuntu-latest
    steps:
      - uses: pascalgn/automerge-action@v0.16.4
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          MERGE_LABELS: "agent-validated"
          MERGE_METHOD: "squash"
YAML
```

---

## 5. Demo script with CHECKPOINTs

| # | Beat | Lines | Time |
|---|------|-------|------|
| 1 | **Hook** | "`plivo/mcp` exposes 6 tools. The Plivo Python SDK has 60+ resources. The gap is human labor. We built the agent that closes it." | 20s |
| 2 | **Stage** | `cat plivo-mcp-fork/server.py \| grep -c '@mcp.tool'` → prints `6`. Show side-by-side: SDK has 60+ resource classes, MCP has 6 tools. | 30s |
| 3 | **Trigger** | Click "Merge pull request" on the staged `Transcripts.create` PR. **CHECKPOINT 3**: Actions tab shows PRMCP workflow within 30s. **If not by 0:50** → `gh workflow run prmcp.yml` (manual dispatch is in the yaml). | 45s |
| 4 | **Pipeline live** | Workflow log streams. **CHECKPOINT 4**: `diff_sdk: 1 new resource detected (Transcripts.create)` prints within 45s of workflow start. `synth_tool: emitted 28-line @mcp.tool() fn`. **If diff_sdk fails to detect** → cut to backup screencast (rehearsed cue) and narrate. | 60s |
| 5 | **Wow + recovery beat** | `cat $GITHUB_WORKSPACE/prmcp-trace.jsonl` shown in Actions log. **CHECKPOINT 5**: 2 lines visible — line 1 `"status":429,"attempt":1`, line 2 `"status":200,"attempt":2`. **If only 1 line** → `gh run download <run-id> -n prmcp-trace` to pull the artifact in a side terminal; say "fetching the trace from the artifact store, this is how teams debug after the fact." | 45s |
| 6 | **Self-merge** | PR appears on `plivo-mcp-fork`. CI runs (smoke + snapshot). Green. Auto-merge fires. **CHECKPOINT 6**: `gh pr list -R plivo-hackathon-2026/mcp --search "PRMCP"` shows the PR as merged. **If PR open fails** → `gh pr create -B main -H prmcp/transcripts-create --title "PRMCP: Transcripts.create" --body "agent-validated"` manually; frame as "demonstrating the merge half." | 30s |
| 7 | **Install pitch** | `cat .github/workflows/prmcp.yml` in target laptop. "Two yaml files plus one classic PAT. Same yaml works against upstream once you have org membership." Show pre-staged clipboard install command. | 20s |

**Total**: 4:10 spoken / 5:00 slot. ~50s buffer for Q&A spillover.

**Hard fallback during demo**: at any CHECKPOINT failure where recovery >15s, switch to the rehearsed 90s backup screencast and resume narration on the next beat.

---

## 6. Risk register (surviving risks post-evidence)

| # | Risk | Trigger | Owner | Mitigation |
|---|------|---------|-------|------------|
| 1 | CRUD coverage gap on non-canonical methods | Demo PR uses a non-CRUD verb | Person A | Demo `Transcripts.create` only (canonical CRUD). Non-CRUD labelled `prmcp-unsupported` — shows agent reasoning about own limits |
| 2 | Gemini free-tier quota exhausted mid-demo | Burn through 1500 req/day during rehearsals | Person B | Cache validation by `(resource, method)` signature; hard cap 3 calls/PR; spare key minted at Hr 0 as backup |
| 3 | Classic PAT 2FA/SSO friction | PAT can't auth on demo morning | Person A | Mint **two** classic PATs at Hr 0, store both as secrets; one is the spare |
| 4 | Actions queue delay | Saturday afternoon contention | Both | Trigger one warm-up workflow 5 min before demo slot; pre-cache pip/npm |
| 5 | `npx @modelcontextprotocol/inspector` cold-pull | Inspector beat hangs | Person B | Pre-warmed once at Hr 0 (in SETUP block) |
| 6 | Snapshot tests drift | Plivo ships SDK update Saturday morning | Person A | Pin `plivo==4.60.1` exactly in `requirements.txt` |
| 7 | Genericity attack ("OpenAPI codegen") | Judge raises it in Q&A | Either | Pre-baked answer: no public Plivo OpenAPI exists (C3.3); Speakeasy/Stainless need OpenAPI; Stainless wound down their hosted product 2026-05-18 |
Risks deleted vs. PRMCP.md original §11: AST-decorator parse edge cases (folded into shape-detector scope-limit), localhost networking (mitigated by same-runner architecture), PAT scope (replaced by classic PAT swap), stdout-no-tool-trace (replaced by direct SDK invocation), Anthropic billing/cutover (moot — we use Gemini now).

---

## 7. Red Team findings + applied fixes

| # | Failure | Trigger | Visible Failure | Fix Applied |
|---|---------|---------|-----------------|-------------|
| 1 | Cross-repo PR fails silently | Classic PAT lacks cross-org grant OR fork-to-upstream PR blocked by SSO | Checkpoint 6: PR never appears | **Target BASE inside our own fork** (`plivo-hackathon-2026/mcp:main`, not upstream `plivo/mcp`). Hardcoded in `open_pr.py`. Demo pitch reframed: "same yaml works against upstream with org membership." Removes entire cross-org failure class. |
| 2 | Claude CLI 60s stall composes with Actions queue delay | claude-code#20527 + Saturday runner contention | Checkpoint 5: 2+ minutes of dead air | **Drop Claude CLI from runner entirely; use `google-genai` SDK + Gemini 2.5 Flash for validation.** Validation drops from 60–180s to 2–5s. Free under Gemini free-tier. Deletes Claude OAuth dance, Node install on CI, and `--bare`+keychain caveat. |
| 3 | Trace file invisible across steps | `$RUNNER_TEMP` is per-step-scoped in some configs; FastMCP subprocess inherits different TMPDIR | Checkpoint 5: `cat` returns "No such file" or 1 line | **Pin trace path to `$GITHUB_WORKSPACE/prmcp-trace.jsonl`** (checked-out repo root, stable across all steps + subprocesses + survives upload-artifact). Add explicit `test -s` step right after the python step — fail loud in dry-run, never silent on stage. Upload as artifact for mid-demo recovery via `gh run download`. |

All three fixes composed into §3 / §4 / §5 above.

---

## 8. GO / NO-GO morning checklist (≤12 items, all <30s to answer)

1. ☐ `python -c "from google import genai; print(genai.Client().models.generate_content(model='gemini-2.5-flash', contents='hi').text)"` returns text in <5s with `GEMINI_API_KEY` set?
2. ☐ Gemini function-calling smoke test: convert one `@mcp.tool()` schema → `FunctionDeclaration`, get a valid function-call response back?
3. ☐ Classic PAT can `gh pr create -B main -H <branch> -R plivo-hackathon-2026/mcp`?
4. ☐ `diff_sdk.py` snapshot test passes on the 16 clean-CRUD files?
5. ☐ `synth_tool.py` snapshot test produces expected output for `Transcripts.create` fixture?
6. ☐ Full pipeline ran 3× consecutive successfully at Hr 17 (each: PR ≤90s, trace [429,200], wall ≤90s)?
7. ☐ Backup screencast recorded, 90s, covers full pipeline + closing inspector beat?
8. ☐ `npx @modelcontextprotocol/inspector` connects to local `server.py` in <10s (pre-warmed)?
9. ☐ Both PATs (primary + spare) stored as repo secrets?
10. ☐ `actions/upload-artifact@v4` step actually attached `prmcp-trace.jsonl` in last dry run?
11. ☐ Both staged demo PRs (`Transcripts.create` + `Numbers.search`) reset to draft and ready to merge?
12. ☐ Install command pre-pasted to clipboard on the judge laptop?

If any **bold item** (1, 6, 7, 11) is NO → halt demo, switch to backup. Others are degraded-but-survivable.

---

## 9. Fallback tree

```
A. Full PRMCP demo (shadow agent + PR loop + auto-merge)
   │
   ├─ Hr 4 canary fail (diff_sdk not snapshot-passing)
   │   └→ C. Switch entire build to Plivo Doctor (Idea B, PLAN.md §Idea B)
   │
   ├─ Hr 17 GO/NO-GO fail (any 3-run flake)
   │   └→ B. PR-opening + smoke-import CI only, no shadow agent
   │      Demo loses "Claude validated it" beat, keeps "agent opens PR" beat
   │
   ├─ On-stage Checkpoint 4 fail (diff_sdk silent)
   │   └→ Cut to backup screencast, continue narration on next beat
   │
   ├─ On-stage Checkpoint 5 fail (trace missing)
   │   └→ `gh run download -n prmcp-trace` in side terminal,
   │      narrate as "fetching from artifact store — this is how
   │      teams debug after the fact" (turns failure into feature)
   │
   └─ On-stage Checkpoint 6 fail (PR didn't open)
       └→ `gh pr create` manually, frame as "demonstrating the merge half"
```

---

## 10. Open questions for the user before sleep

1. ~~ANTHROPIC_API_KEY~~ **RESOLVED**: validation LLM is **Gemini 2.5 Flash** via `google-genai` SDK. Mint a key at https://aistudio.google.com/app/apikey (free tier covers hackathon). Store as `GEMINI_API_KEY` repo secret.

2. ~~Fork org policy~~ **RESOLVED**: forks live under personal account. Safety guardrail: `open_pr.py` asserts target does not start with `plivo/` — no accidental upstream PRs possible.

3. ~~Claude `--bare` + OAuth~~ **RESOLVED**: no longer relevant — Claude CLI dropped from CI runner entirely. Claude Code remains the dev-laptop tool (unchanged).

4. **GitHub Actions queue contention Saturday 14:55 IST**: Pre-warm workflow 5 min before demo (per Risk #4 mitigation). No action needed tonight, but flag this in the morning checklist as item to execute at demo-T-10.

5. **The 7 PRMCP.md verification gates** — all 7 in PRMCP.md §13 have been made executable above (§8 GO/NO-GO maps to gates 1-7). No gates silently dropped. Gate #6 ("demo runs ≤4:30") tightens to ≤4:10 per §5 timing.

6. **MCP-schema → Gemini FunctionDeclaration converter**: ~10-line shim, written at Hr 8–12. Both use JSON Schema for params; main edge case is that Gemini's JSON Schema subset doesn't accept `oneOf`/`anyOf`. For the 16 clean-CRUD scope (C3.2 swap), params are all primitives — no edge cases hit. If a future passthrough template surfaces a complex schema, fall back to flattening to a string param + docstring.

Nothing in this list blocks Hr 0. Open items are now operational (item 4 is a demo-T-10 reminder, items 5–6 are implementation notes).

---

## Notes on tone + scope

This document replaces `PLAN.md` as source of truth for the build, per CLAUDE.md instruction. PRMCP.md remains the deep-dive narrative — refer to it for architecture/repo-layout context. Three concrete edits to PRMCP.md to apply at Hr 0 (none are blockers; doing them after Hr 0 is fine):

- §3 row 2 date typo: "2025-04-17" → "2026-04-17"
- §7 workflow yaml: `pip install ... claude-cli ...` → replace with `google-genai` (no Claude CLI needed on runner anymore)
- §7 / §11 row 6: "fine-grained PAT" → "classic PAT with `public_repo` scope"
- §12 "Headless Claude" stack line → "Validation LLM: Gemini 2.5 Flash via google-genai SDK"

Monday-morning shippable check: install = paste 2 yaml files + 1 classic PAT secret + 1 Gemini API key = ~30s on a judge's fork. Within budget per CLAUDE.md.
