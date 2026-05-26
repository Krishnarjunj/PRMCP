# PRMCP — Full Research & Build Plan

> The agent that maintains `plivo/mcp` for you. Watches the Plivo Python SDK, auto-generates the matching FastMCP tool, validates it by running Claude against it, opens a PR, self-merges on green.

This document is the standalone deep-dive on Idea C from `PLAN.md`. It exists because PRMCP is the recommended primary path for the Plivo Hackathon 2026 ("Plivo By Agents" track) and the original plan's assumptions about it were wrong in three load-bearing places — corrected and re-verified below.

---

## 1. The pitch in one line

**A GitHub Action + Claude-driven shadow agent that watches `plivo/plivo-python` for new SDK resources/methods, generates the corresponding `@mcp.tool()` function for `plivo/mcp`, validates the new tool by invoking Claude against it, opens a self-labelled PR, and auto-merges on green CI.**

Install: copy one workflow yaml, paste one PAT secret.

---

## 2. Why this idea wins the "By Agents" track

- **Solves judges' own pain.** The four judges are Plivo engineers. The current `plivo/mcp` exposes only **6 tools** while `plivo-python` covers **60+ resources**. That gap is itself the bug PRMCP fixes. The hackathon's stated theme — "Agents becoming first class engineers working in parallel with us" — is literally PRMCP's job.
- **Three nested agent loops, all visible on stage.** Claude Code writes PRMCP → PRMCP runs Claude as a shadow agent against the synthesized tool → that tool invokes Plivo's SDK. Judges see all three.
- **Sharp answer to the "this is just OpenAPI codegen" attack.** We have **no OpenAPI spec to consume** (none exists publicly). We're doing AST → MCP, which is materially harder. Existing tools like `openapi-mcp-generator`, Stainless, Speakeasy all start from OpenAPI; none do (a) SDK AST diffing, (b) self-validating PR loops, (c) long-lived watcher operation.
- **Demo-guideline #4 ("graceful self-recovery") is built into the flow**, not staged on top: the shadow agent's first invocation hits an injected 429, backs off, retries, succeeds. This is shown live in the workflow log.
- **"Monday morning shippable" is literally a 2-line workflow paste.**

---

## 3. Verified facts that reshaped the plan

Three corrections from a second-pass Explore agent. Citations below the table.

| # | Original assumption | Verified reality | Implication |
|---|---|---|---|
| 1 | `plivo/mcp` is TypeScript | **Python + FastMCP, single-file `server.py`, no tests, no CI** | Codegen target is Python `@mcp.tool()` decorators wrapping `plivo.RestClient()` calls; we get to introduce missing tests/CI as part of the demo |
| 2 | We diff Plivo's OpenAPI spec | **No public Plivo OpenAPI spec anywhere** | Instead: AST-parse `plivo/plivo-python`. The SDK has a uniform two-class pattern (`Resource` + `Resources`) over the standard 5 verbs (`.create/.get/.list/.update/.delete`), statically parseable with `ast` |
| 3 | We need a GitHub App | **App requires admin install + webhook hosting; blocked on real `plivo/*` repos** | Use GitHub Actions + PAT instead. No app registration, no webhooks, no admin approval. Judge install = paste yaml + add secret |

Other confirmed facts:
- `plivo-python` ships releases every 1–3 months (most recent: 4.60.1, 2025-04-17). Frequent enough that PRMCP would actually fire in production.
- `claude --bare -p "..." --mcp-config <file> --output-format json --allowedTools "Bash,Read"` is a real, documented invocation. Caveat: stdout JSON does NOT include a tool-call trace — we instrument the FastMCP server itself to write `/tmp/prmcp-trace.jsonl`, which becomes proof-of-invocation.

Sources:
- `plivo/mcp` repo: https://github.com/plivo/mcp
- `plivo/plivo-python` repo: https://github.com/plivo/plivo-python
- `plivo-python` releases: https://github.com/plivo/plivo-python/releases
- FastMCP tool docs: https://gofastmcp.com/servers/tools
- Claude Code headless mode: https://code.claude.com/docs/en/headless
- GitHub Actions cross-repo PR perms: https://docs.github.com/en/actions/using-jobs/assigning-permissions-to-jobs
- GitHub App install policy (2025): https://github.blog/changelog/2025-12-01-block-repository-admins-from-installing-github-apps-now-generally-available/
- Existing OpenAPI→MCP generators (so we know what we are NOT): https://github.com/harsha-iiiv/openapi-mcp-generator, https://www.speakeasy.com/mcp/tool-design/generate-mcp-tools-from-openapi, https://www.stainless.com/docs/guides/generate-mcp-server-from-openapi/

---

## 4. Architecture

```
┌──────────────────────────┐    PR merged      ┌────────────────────────────┐
│ plivo-python-fork (ours) │ ───────────────▶  │ GitHub Actions: prmcp.yml  │
└──────────────────────────┘                   │  - checkout fork           │
                                               │  - run diff_sdk.py         │
                                               │  - run synth_tool.py       │
                                               │  - run shadow_agent.py     │◀──┐ logs
                                               │    (spawns local FastMCP)  │   │
                                               │  - run open_pr.py (PAT)    │   │
                                               └──────────────┬─────────────┘   │
                                                              │ creates PR      │
                                                              ▼                 │
                                               ┌────────────────────────────┐   │
                                               │ plivo-mcp-fork (ours)      │   │
                                               │  + new @mcp.tool() fn      │   │
                                               │  + label: agent-validated  │───┘
                                               │  CI smoke import → green   │
                                               │  auto-merge action fires   │
                                               └────────────────────────────┘
```

The diagram has three first-class actors:
1. **The watched repo** (`plivo-python-stub` — our fork or a tiny stub).
2. **The agent** (Actions workflow + Python scripts in `prmcp` repo).
3. **The target repo** (`plivo-mcp-fork`).

Plus one observer that's only visible to PRMCP itself: the **shadow Claude session** invoked headlessly inside the runner.

---

## 5. Repo setup (Hr 0 of the build)

| Repo | Purpose | Source |
|---|---|---|
| `<our-org>/plivo-python-stub` | Watched repo. Either a fork of `plivo/plivo-python` or a tiny stub with one fake resource to make the demo deterministic. | Fork or new |
| `<our-org>/plivo-mcp-fork` | Target repo for generated PRs. Fork of `plivo/mcp`. We add a `.github/workflows/auto-merge.yml` here. | Fork |
| `<our-org>/prmcp` | The agent itself: workflow + Python scripts + templates. | New |

PAT setup: fine-grained PAT with **write access only to `plivo-mcp-fork`**. Stored as `PAT_TOKEN` in `plivo-python-stub`'s Actions secrets. README documents this explicitly for the demo.

---

## 6. `prmcp` repo file structure

```
prmcp/
├── .github/workflows/
│   └── on-sdk-merge.yml          # reusable workflow callers paste into their fork
├── src/prmcp/
│   ├── diff_sdk.py               # walk plivo-python/plivo/resources/*.py with `ast`,
│   │                             # extract {resource, method, params, http_verb_guess}
│   │                             # diff vs baseline manifest stored in repo
│   ├── synth_tool.py             # Jinja → emits a @mcp.tool() function per new entry
│   ├── shadow_agent.py           # spawn local FastMCP w/ new tool, call `claude --bare -p`,
│   │                             # read invocation log from server-side instrumentation
│   ├── open_pr.py                # PyGithub: branch, apply patch, push, open PR + labels
│   └── templates/
│       ├── tool_create.py.jinja  # template for .create()-shaped tools
│       ├── tool_get.py.jinja     # template for .get(id)-shaped tools
│       ├── tool_list.py.jinja
│       ├── tool_update.py.jinja
│       └── tool_delete.py.jinja
├── fixtures/
│   ├── baseline_manifest.json    # last-seen resource/method/param tree
│   ├── sample_new_resource.py    # a "Transcripts" resource we drop into plivo-python-stub
│   │                             # during the demo to trigger the pipeline
│   └── expected_tool.py          # snapshot test: what synth should produce
├── tests/
│   └── test_diff_synth.py        # pytest: fixture-based snapshot tests
└── README.md                     # install: copy workflow + add PAT_TOKEN secret
```

---

## 7. Workflow yaml — what judges literally install

```yaml
# .github/workflows/prmcp.yml — paste into your SDK repo
name: PRMCP
on:
  pull_request:
    types: [closed]
    branches: [main, master]
jobs:
  prmcp:
    if: github.event.pull_request.merged == true
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 2 }
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install prmcp claude-cli plivo fastmcp
      - run: prmcp run --target-repo ${{ vars.MCP_REPO }} --pat ${{ secrets.PAT_TOKEN }}
```

Companion on `plivo-mcp-fork`:

```yaml
# .github/workflows/auto-merge.yml
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
```

---

## 8. Tool synth — what a generated `@mcp.tool()` looks like

Input (parsed from `plivo/resources/transcripts.py`):
```python
class Transcripts(PlivoResourceInterface):
    @validate_args(call_uuid=[required(of_type(str))], language=[optional(of_type(str))])
    def create(self, call_uuid, language="en-US"):
        ...
```

Generated tool (via `tool_create.py.jinja`):
```python
@mcp.tool()
def transcripts_create(call_uuid: str, language: str = "en-US") -> dict:
    """Create a transcript for the given Plivo call.

    Auto-generated by PRMCP from plivo-python@<sha>. Do not edit by hand.
    """
    client = plivo.RestClient(auth_id=os.environ["PLIVO_AUTH_ID"],
                              auth_token=os.environ["PLIVO_AUTH_TOKEN"])
    return client.transcripts.create(call_uuid=call_uuid, language=language)
```

Five Jinja templates cover the canonical CRUD shapes. Anything that doesn't match one of those five is labelled `prmcp-unsupported` and surfaces the agent's reasoning about its own limits — which strengthens the pitch rather than weakens it.

---

## 9. Hour-by-hour build plan (24 hr, pair, both heavy Claude Code users)

| Hr | Person A | Person B | Riskiest? |
|----|----------|----------|---|
| 0–2 | Fork `plivo-python` + `plivo/mcp` into our org. Mint PAT, store as repo secret. | Get `plivo/mcp`'s existing 6 tools running locally with FastMCP + `mcp inspector`. Capture baseline tool fixture. | No |
| 2–5 | Build `diff_sdk.py`: AST-walk `plivo/resources/*.py`, emit manifest JSON of `{resource, method, params, decorator_args}`. Snapshot-test against current SDK. | Build `synth_tool.py` + 5 Jinja templates. Snapshot-test against existing `send_sms` / `make_call` for parity. | **Yes** — AST edge cases (decorators, dynamic methods, `@validate_args`). Mitigation: scope to the 5 canonical CRUD methods; flag everything else as `prmcp-unsupported` rather than guess. |
| 5–8 | Compose `diff_sdk → synth_tool` end-to-end. Hand-craft a fake "Transcripts" resource in `plivo-python-stub`, verify pipeline emits the correct `@mcp.tool()` function. | Build `open_pr.py` with PyGithub. Open a real PR on `plivo-mcp-fork` with the synthesized tool. Label it `prmcp-generated`. | No |
| 8–12 | Instrument the local FastMCP `server.py`: every tool invocation appends `{tool, args, ts, result}` to `/tmp/prmcp-trace.jsonl`. This is our proof-of-invocation. | Build `shadow_agent.py`: spin up the candidate `server.py` as a subprocess; write a temp `.mcp.json`; invoke `claude --bare -p "Use <tool> with these params: {...}" --mcp-config tmp.mcp.json --output-format json`; assert `/tmp/prmcp-trace.jsonl` has an entry for the new tool. | **Yes** — `claude -p` rate limits + headless config quirks. Mitigation: cache validation by `(resource, method)` signature; budget cap of 3 validation calls per PR. Backup: skip shadow agent, fall back to a unit-test smoke-import only — degraded but still demoable. |
| 12–15 | Compose the full workflow yaml. End-to-end live test: trigger by merging a staged PR on `plivo-python-stub`; watch Actions run; verify a PR opens on `plivo-mcp-fork`. | Wire CI on `plivo-mcp-fork`: smoke `python -c "import server"` + `pytest -k generated` on the synth'd tool. | No |
| 15–18 | Build `auto-merge.yml` on `plivo-mcp-fork`: when PR has both `agent-validated` label and green CI, squash-merge automatically. | Wire **intentional recovery beat**: shadow agent's first invocation injects a 429 (mock); agent retries with backoff; second call succeeds. Log both attempts to trace. This is the demo's "graceful recovery." | No |
| 18–21 | Stage the demo: prepare 2 candidate "new endpoint" PRs in `plivo-python-stub` (a `Transcripts.create` and a `Numbers.search`). Practice triggering each. Capture screen recordings as backup. | Polish README — copy-paste install block, GIF screencast, one-line "what PRMCP does," failure-mode docs. | No |
| 21–23 | Demo rehearsal #1 + #2 with stopwatch. Refine the talking script. | Final-pass `pytest` over all snapshot tests. Verify deterministic output. | No |
| 23–24 | Demo rehearsal #3. Backup video re-recorded if anything drifted. | Buffer. | No |

**Hard cutover at Hr 18** if shadow agent isn't end-to-end working: drop shadow agent, ship the PR-opening pipeline with smoke-import CI only. The demo loses the "Claude validated it" beat but keeps the "agent opens PR on agent's behalf" beat. Still wins the "By Agents" track.

**Hr-4 canary**: if `diff_sdk.py` isn't snapshot-passing on the existing `plivo-python` resources, abandon PRMCP and switch to Idea B (Plivo Doctor MCP) — see `PLAN.md`.

---

## 10. Demo script (5 min slot, target 3:30 spoken, ~30s buffer for Q&A spillover)

1. **(20s) Hook**: "`plivo/mcp` exposes 6 tools. The Plivo Python SDK has 60+ resources. The gap is human labor that doesn't scale. We built the agent that closes that gap automatically."
2. **(30s) Stage**: Show `plivo-python-stub` and `plivo-mcp-fork` side-by-side. Show current `server.py` has 6 `@mcp.tool()` functions.
3. **(45s) Trigger**: Merge a pre-staged PR on `plivo-python-stub` that adds `Transcripts.create()`. Actions tab pops; `PRMCP` workflow appears. Open it.
4. **(60s) Pipeline live**: Workflow log streams: `diff_sdk: 1 new resource detected (Transcripts.create)`. `synth_tool: emitted 1 new @mcp.tool() fn (28 lines)`. `shadow_agent: spawning FastMCP server...`. `claude -p invoked with new tool config`.
5. **(45s) Wow + recovery beat**: Shadow-agent log shows attempt 1 → 429 → backoff → attempt 2 → success. `/tmp/prmcp-trace.jsonl` displayed: confirmed tool invocation with real args. PR opens on `plivo-mcp-fork` with `agent-validated` label.
6. **(30s) Self-merge**: CI runs (smoke + snapshot). Green. Auto-merge action fires. `plivo-mcp-fork`'s `main` now has 7 tools, not 6. Run `mcp inspector` against it to prove the new tool is live.
7. **(20s) Install**: "Two lines of yaml + one PAT. Monday morning, paste this into `plivo/plivo-python` and `plivo/mcp` and the lag disappears forever."

---

## 11. Risks & mitigations (refined with verified facts)

| # | Risk | Likelihood | Mitigation |
|---|---|---|---|
| 1 | AST diffing misses non-canonical methods (e.g. `validateNumbers()` that doesn't fit CRUD) | Medium | Scope to the 5 canonical shapes; emit `prmcp-unsupported` label on the PR for unknown shapes — judges *see* the agent reasoning about its own limits |
| 2 | Cannot install on real `plivo/plivo-python` mid-demo | Certain | Use our fork. Frame: "production-ready, awaiting maintainer adoption." |
| 3 | `claude -p` rate-limited or flaky | Medium | Cache per `(resource, method)` signature. Hard cap at 3 validation invocations per PR. Fallback: smoke-import CI |
| 4 | Shadow agent JSON output has no tool-call trace | Confirmed | Server-side instrumentation writes `/tmp/prmcp-trace.jsonl`; PRMCP parses *that*, not stdout |
| 5 | Actions runner can't reach localhost for FastMCP | Low | Both shadow agent + FastMCP server run on the same runner; use `127.0.0.1`. No external networking needed |
| 6 | PAT scope too broad → security pushback | Low | Use fine-grained PAT with write access only to `plivo-mcp-fork`. Document this clearly in README |
| 7 | `@validate_args` decorator parsing breaks on edge cases | Medium | Try decorator AST first; fall back to `inspect.signature` of function source string; final fallback: `params: []` with `prmcp-incomplete-params` label |
| 8 | Genericity attack: "this is just OpenAPI-to-MCP codegen" | Low | We have NO OpenAPI input — AST → MCP is materially harder. We also (a) validate by running an LLM, (b) self-merge PRs, (c) operate as a long-lived watcher. Three distinguishers, each demoed live |

---

## 12. Stack — all free, all verified

- **Language**: Python 3.11 (matches `plivo/mcp` + `plivo-python`).
- **Libs**: `ast` (stdlib), `jinja2`, `PyGithub`, `fastmcp`, `plivo` SDK, `pytest`.
- **Codegen target**: `@mcp.tool()` decorated functions in `server.py` style.
- **Headless Claude**: `claude --bare -p ... --mcp-config ... --output-format json --allowedTools "Bash,Read"`. Burned against the user's existing Claude Code account.
- **Hosting**: Zero. Everything runs in GitHub Actions runners + the user's MacBook locally. No Cloudflare Tunnel needed.
- **Cost**: ₹0. Plivo trial creds optional — shadow agent doesn't need to actually call Plivo's API, it just needs to invoke the new MCP tool, which the FastMCP server can mock locally for the demo.

---

## 13. Verification — acceptance gates before declaring done

1. End-to-end happy path: merge staged PR on `plivo-python-stub` → within 90s, new PR opens on `plivo-mcp-fork` with the generated `@mcp.tool()` function for `Transcripts.create`.
2. Generated tool passes `python -c "from server import *"` (smoke import).
3. Generated tool passes a snapshot test in `tests/test_diff_synth.py`.
4. Shadow agent's `/tmp/prmcp-trace.jsonl` shows ≥1 entry naming the new tool, including the staged retry-after-429 recovery beat.
5. Auto-merge action fires on `agent-validated` label + green CI.
6. Whole demo end-to-end runs in ≤4:30 on a stopwatch with one practice. Backup screencast recorded.
7. README contains a copy-pasteable `prmcp.yml` and a 4-step install. A judge can install on their own fork in <60s.

---

## 14. Open questions to resolve at kickoff (Fri 3PM)

- Can we get a `plivo-python` fork into the `plivo-hackathon-2026` GitHub org, or do we keep it in a personal account?
- Is there an internal Plivo OpenAPI spec we could use instead of AST parsing? (Probably not, but worth a 60-second ask.)
- Does the Plivo eng team have a strong opinion on the auto-merge labels? (We can rename `agent-validated` → whatever they bikeshed.)

None of these block the build; they only affect framing.
