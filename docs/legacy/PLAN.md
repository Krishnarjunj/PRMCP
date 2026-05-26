# Plivo Hackathon 2026 — Idea Audit

## Context (Step 1)

**Hackathon**: Plivo Hackathon 2026 — "Plivo For Agents, Plivo By Agents". On-site, Fri 3PM → Sat 3PM (24 hrs of build). Demos Sat 3PM, 5 min demo + 2 min Q&A.

**Team**: Pair, both heavy Claude Code users, no fixed Plivo product depth, open on track. Fresh slate.

**Judging**: 4 internal Plivo engineers (Mike, Likith, Manish, Ayush). Internal audience. No public vote. Demo guidelines explicitly weighted:
1. One-line hook (what / who).
2. One real Plivo pain point.
3. Live agent demo end-to-end — show the prompt, the tool calls, the result.
4. **Show one failure mode handled gracefully, agent self-recovered (carrier error / retry / budget cap).**
5. Shippability — install command, "Monday morning we can deploy this."

**Stack**: Claude Code / Cursor / Codex provided. Plivo accounts available. Free for judges to evaluate is implicit (they're on Plivo's network).

**Two tracks** (from site-main checkin code):
- `for-agents` — Plivo as a service callable end-to-end by an LLM agent.
- `by-agents` — Tooling that lets Plivo engineers ship 100x autonomously.

**Landscape (verified)**:
- `github.com/plivo/mcp` exists but only covers `send_sms / make_call / create_application / create_endpoint / get_cdr / get_mdr`. **No Voice Agents / Audio Streaming support.** Many teams will spot this gap → "build an MCP" is the lowest-effort generic submission.
- No `plivo-cli` exists. Twilio CLI has MCP, Plivo doesn't.
- Plivo's flagship 12-month launch is **Voice Agents (vibe-agent)** — no-code builder, Deepgram STT + ElevenLabs TTS + Plivo audio streaming. No native testing / observability / regression story.
- Stripe Projects (projects.dev): scoped agent credentials + per-agent spend caps. Plivo has zero equivalent.
- Cloudflare's pattern (Agents Week 2026): MCP that exposes API via TypeScript code execution rather than tool enumeration (81% token savings).
- Plivo already integrates *outbound* MCP connectors (agents call HubSpot/Salesforce/Slack/Zendesk from a voice call) — but no *inbound* developer-facing agent tooling beyond the basic MCP.

**Open questions** (none blocking — the user said "anything feasible, claudemaxxable, win-first"):
- Confirmed: pair, both claude-maxxers, open track, fresh slate.

---

## Diverge → Killed list (Steps 2–3)

Raw count: 35 candidates generated. Killed:

| # | Idea | Kill reason |
|---|---|---|
| 1 | "Voice Agents MCP server" filling the plivo/mcp gap | **Generic** — every other team will pitch this; the gap is the obvious play |
| 3 | Plivo CLI with Stripe-Projects-style scoped creds | **Generic + scope** — useful but 5+ teams will pitch a CLI; full Stripe-Projects clone in 24 hr is too big |
| 8 | "Number provisioning MCP" | **Generic** — folded into every MCP pitch |
| 11 | Carrier-error decoder MCP | **Generic** — folded into every MCP pitch |
| 12 | Universal voice-agent gateway (provider-agnostic SDK) | **Generic + wrapper** |
| 14 | Voice-agent prompt versioning | **Wrapper** — mostly git/UI over prompts |
| 15 | Conversation summarizer MCP | **Wrapper** — pure LLM call |
| 17 | On-call agent for Plivo alerts | **Generic + existence** — Resolve.AI, PagerDuty AIOps already exist; OSS variants like `incident-bot` cover this |
| 21 | SDK generator agent from OpenAPI | **Existence** — `openapi-generator`, Stainless, Speakeasy all do this |
| 23 | "Ask the docs" MCP | **Generic + wrapper** — RAG over docs is the canonical wrapper |
| 24 | Cost-impact analyzer for code changes | **Feasibility** — needs realistic pricing model + real PRs in 24 hr |
| 25 | Migration agent (old API → new) | **Feasibility** — needs source code of a customer integration as input |
| 26 | Voice-control Claude Code via Plivo call | **Demo test** — gimmick; judges are engineers, won't translate to shippable |
| 27 | Agent-to-agent voice IPC | **Gimmick** — funny, not shippable |
| 28 | Live customer-call shadow agent | **Generic** — Gong, Fireflies, Modjo already exist; consent/recording overhead too high for 24 hr |
| 30 | Carrier CSR negotiation agent for port-in | **Demo test + scope** — too narrow, single workflow, judges can't easily verify |
| 31 | Voice-agent observability metrics MCP | **Generic** — folded into other MCP pitches |
| 32 | `plivo tail` logs MCP | **Generic** — folded into other MCP pitches |
| 33 | Voice-driven Plivo dashboard | **Gimmick** + wrapper |
| 34 | SMS A/B testing agent | **Narrow** — single-channel optimizer, weak wow |
| 35 | Replay-attack fraud canary | **Feasibility** — needs realistic fraud signals + judges can't grade adversarial scenarios live |

**Survivors carried into Step 4**: 4 ideas (audited below). They cover both tracks so the team can pick on Friday 3PM after kickoff vibes.

---

## Step 4 — Deep Feasibility Audit

### Idea A: **AgentDouble** — *Cypress for Plivo Voice Agents*
**One-line pitch**: A CLI + dashboard that runs a YAML rubric of synthetic LLM-driven phone calls against a Plivo voice agent and grades it on latency, intent-coverage, hand-off, and regression-vs-last-run.

- **User & moment**: A Plivo customer (or internal team) just edited a vibe-agent prompt. They have no idea if it regressed the "transfer to human when angry" flow until the next real customer complains. Today, the answer is "call the bot from your iPhone five times."
- **Why it wins**:
  - Hits judging-criterion #3 (live agent demo) perfectly — the demo *is* a swarm of agents talking to the product.
  - Hits #4 (graceful failure recovery) by design — the harness reruns flapping tests with backoff, classifies error vs flake.
  - Hits #5 (shippable) — `npx @plivo/agentdouble run rubric.yaml`. Plivo's vibe-agent customers want this on day one.
  - Visual wow: a grid of 30 simulated calls running concurrently, each tile coloring green/red live, replayable transcript on click.
- **Why not generic**: nearest existing things are **Vapi's `assistant.test`** (single-shot LLM eval, not phone-bound), **Cekura** (voice-agent QA, paid SaaS, not Plivo-native), and **Coval** (voice-agent observability, no rubric-driven regression). None of them are: (a) Plivo-native using Plivo's own audio streaming as both caller AND callee, (b) free + OSS, (c) judge-runnable in 30 seconds.
- **Why not a wrapper**: the LLM is one of four parts. The other three are: a **scheduler** that drives N concurrent Plivo outbound calls into a target Plivo voice agent; a **rubric engine** that scores deterministically (transcript regex, latency ms, hand-off-event observed, audio silence > X ms) before any LLM judging; a **call-graph diff** that compares this run's transcripts to a baseline run (anchored by intent labels, not text equality). Pull the LLM and you still have: a parallel call driver + deterministic grader + diff — already useful.
- **Stack (all free)**:
  - `plivo-node` SDK (MIT, free). Audio Streaming API on a trial Plivo account.
  - `@anthropic-ai/sdk` via `claude -p` for the synthetic-caller persona + the LLM-judge fallback (Claude Code accounts provided).
  - `pnpm` workspace + `vitest` for the rubric runner.
  - `Hono` server on `localhost:3000`, SQLite for run history (no cloud).
  - `Vite` + `React` + `xterm.js` for the dashboard (live SSE).
  - `cloudflared tunnel` (free) to expose for judges if they want to run remotely — already used by the site-main repo so it's blessed.
  - Compatibility: pure Node 20 + Vite. Runs on a MacBook. No GPU.
- **Build plan (24 hr, pair)**:
  - Hr 0–2: Scaffold monorepo. Spin up a target Plivo voice agent (vibe-agent UI) that does a "pizza-order" flow — this is what we test against. Wire one outbound Plivo call from Node.
  - Hr 2–5: Synthetic caller — Claude as the customer persona, streamed into Plivo's audio stream, TTS via ElevenLabs free or Plivo built-in. *Riskiest step.* Fallback: pre-recorded WAV "customer turns" instead of live LLM TTS — degraded but still demoable.
  - Hr 5–8: Rubric engine — YAML schema (`expects: { intent: "transfer", latency_ms_under: 800 }`), deterministic checks first, LLM-judge as last resort.
  - Hr 8–12: Concurrency — run 20 calls in parallel, store transcripts in SQLite.
  - Hr 12–16: Dashboard — grid view, click to replay transcript with timing, diff view.
  - Hr 16–20: Failure recovery — auto-retry-with-backoff on `5xx` from Plivo, classify carrier error vs assistant error vs flake. **This becomes the demo's "graceful failure recovery" beat.**
  - Hr 20–22: Polish demo script + record a backup video.
  - Hr 22–24: Rehearse 5+2 demo. Buffer.
- **Demo script (3-min flow)**:
  1. (15s) "We built a vibe-agent yesterday. Then we edited the prompt. Did we break it? Today the answer is calling it from your phone. Watch."
  2. (45s) `agentdouble run pizza.yaml` — terminal scrolls, dashboard pops open, 30 tiles spawn live. 28 green, 2 red.
  3. (60s) Click a red tile → replay shows the agent failed to escalate to human when the synthetic caller said "this is the third time I'm calling." Show the rubric line that caught it.
  4. (30s) **Wow beat**: One tile flashes yellow → "Carrier returned 487, retried, passed on second attempt." Click → see the auto-recovery log. (This *is* demo guideline #4.)
  5. (30s) `git revert` the prompt → re-run → tile flips green. CI integration shown: `agentdouble ci --baseline=main`.
  6. (10s) Install line: `npx @plivo/agentdouble init`.
- **Risks & mitigations**:
  1. *Plivo Audio Streaming latency too high for live LLM-TTS roundtrip* → fallback to pre-recorded synthetic-customer audio per turn. Still a real call, still scoreable.
  2. *Concurrent outbound calls hit Plivo trial rate limits* → demo with 5 concurrent, show the grid scaling claim as a number, not 30 live.
  3. *LLM judge disagrees with itself across runs* → deterministic checks first (regex / latency / event presence); LLM judge only as tiebreaker and shown to the user.
  4. *vibe-agent target itself is buggy and skews results* → ship a second mode where target is any HTTP webhook, not just Plivo voice — broadens use case anyway.

---

### Idea B: **Plivo Doctor** — *MCP that diagnoses why a call/SMS failed and self-heals*
**One-line pitch**: An MCP server that an agent calls *after* a Plivo API error or a bad CDR; it reconstructs the call graph, identifies the failure point, and either retries with a corrected request or hands a structured RCA back to the agent.

- **User & moment**: An LLM agent (e.g. a Voice Agents user's orchestrator, or a Claude Code session debugging an integration) calls `make_call` and gets `400 invalid_from_number`. Today: the agent loops, retries the same thing, exhausts tokens. With Doctor: the agent calls `plivo_doctor.diagnose(error_id)`, gets back `{cause: "from_number not verified for trial account", fix: "verify at /verify or use 'pretend' sandbox", action: "retry_with_sandbox_from"}`.
- **Why it wins**:
  - Directly addresses demo guideline #4 (graceful self-recovery) — it *is* the recovery mechanism.
  - Hits #3 (live tool calls visible) — judges see the agent call Doctor, see the diagnosis, see the retry succeed.
  - "Monday morning" appeal — every Plivo customer with an agent integration has hit this.
- **Why not generic**: Two nearest things — Twilio's status-callback URL + their `errors` REST endpoint, which returns a one-line message and a docs URL only (no action graph). And Vonage's `voice/cdr` lookup, which is data-only. Neither produces an **agent-consumable action plan** keyed by error class. None do CDR-replay reconstruction.
- **Why not a wrapper**: the core is a hand-curated **error → diagnosis → action** decision graph for the top 30 Plivo error codes + a CDR/MDR replay engine that walks SIP states (`Trying → Ringing → BYE` vs `Trying → 487`) to localize the failure step. LLM is just used to phrase the action back to the calling agent. Strip the LLM: you still have an MCP tool returning structured `{cause, fix, retry_payload}`.
- **Stack (all free)**:
  - `@modelcontextprotocol/sdk` (MIT) — official MCP SDK.
  - `plivo-node` for CDR/MDR fetches.
  - YAML rule files for the error → fix graph (start with ~30 hand-curated rules from Plivo's public error reference).
  - `claude -p` for natural-language phrasing of the diagnosis only.
  - Distribute as `npx @plivo/doctor-mcp` + a `.cursor/mcp.json` / Claude Code MCP config snippet.
- **Build plan (24 hr, pair)**:
  - Hr 0–3: Scrape & encode Plivo's public error code reference into YAML rules. Pair-split: one person does Voice errors, one does Messaging.
  - Hr 3–8: MCP server with three tools: `diagnose(error_or_call_id)`, `replay(call_uuid)`, `propose_retry(call_uuid)`.
  - Hr 8–14: CDR/MDR replay — pull the call's CDR, reconstruct the timeline, mark the failure step. *Riskiest step* (depends on Plivo CDR detail). Fallback: skip replay, ship diagnosis + retry only.
  - Hr 14–18: Wire a "broken integration" demo project that intentionally hits 5 different failure modes (bad from, throttle, blocked country, wrong webhook, SIP 487).
  - Hr 18–22: Demo polish + Claude Code session recording showing the recovery loop.
  - Hr 22–24: Rehearse.
- **Demo script (3-min flow)**:
  1. (20s) "Show me an agent calling a Plivo API and crashing on a real error." Run `claude -p "send an SMS via Plivo to +1555..."` in a Claude Code session. Fails.
  2. (60s) "Now I add one MCP to its config." Add `plivo-doctor` MCP. Re-run. Agent crashes → calls `plivo_doctor.diagnose` → gets `{cause: "+1555 is a 555 reserved range", fix: "use a real test number", retry_payload: {to: "+18005551212"}}` → retries → succeeds. *All visible in the terminal.*
  3. (45s) Cycle through 3 more error classes (throttle, bad webhook, SIP 487) — Doctor self-heals each.
  4. (30s) **Wow beat**: A live phone call that drops mid-stream → CDR replay → Doctor shows "BYE from carrier at 11s, retry on backup route" → second call placed → succeeds. *Demo guideline #4 met explicitly.*
  5. (15s) Install: `npx @plivo/doctor-mcp` + one-line MCP config.
- **Risks & mitigations**:
  1. *Plivo's public error reference is shallow* → focus on the 10 errors we can reproduce in a sandbox; depth > breadth.
  2. *CDR replay is too detailed to ship in 24 hr* → drop the SIP state machine, show just the headline `final_status / hangup_cause / failed_step` triple.
  3. *Judges say "this is just a lookup table"* → the live retry-and-succeed loop is the answer — it's a self-healing agent, not a docs search.

---

### Idea C: **PRMCP** — *The agent that maintains `plivo/mcp` for you* (EXPANDED, FEASIBILITY-VERIFIED)

> Status: this section was rewritten after a second-pass Explore agent verified the actual code surface. Original assumptions about TypeScript / OpenAPI / GitHub App were wrong — corrected below with sources.

**One-line pitch**: A GitHub Action + agent that watches `plivo-python` SDK PRs, statically diffs the resource classes, generates the corresponding FastMCP tool on `plivo/mcp`, runs a headless Claude shadow-agent against the new tool to validate it actually works, opens an `agent-validated` PR, and auto-merges on green CI.

#### Verified facts that reshape the plan
1. **`plivo/mcp` is Python + FastMCP, not TypeScript.** Single-file `server.py`. Tools registered via `@mcp.tool()` decorator wrapping `plivo.RestClient()` calls. No tests, no CI, no LICENSE confirmed. Implication: our codegen target language is Python; we get to *introduce* the missing tests/CI as part of the demo.
2. **No public Plivo OpenAPI spec anywhere.** Not in `plivo/mcp`, not in `plivo/plivo-python`, not on the docs site. The original plan's "OpenAPI diff" pipeline is dead. Replacement: **AST-parse `plivo/plivo-python`** — it has a consistent two-class pattern per resource (`Resource` subclass of `PlivoResource` + `Resources` subclass of `PlivoResourceInterface` exposing `.create/.get/.list/.update/.delete`). This is statically parseable without executing the SDK. Releases land every 1–3 months — frequent enough to be a real signal.
3. **GitHub App is overkill and probably blocked.** A 24-hour-old GitHub App cannot be installed on `plivo/plivo-python` without org admin approval (per GitHub's 2025 install policy). Replacement: **GitHub Action + PAT secret**. Workflow runs in our fork of `plivo-python`; on PR-merge it generates the patch and opens a PR on our fork of `plivo/mcp` using a PAT with `repo` scope. Judges install with two lines: copy the workflow yaml, paste a PAT secret. This is dramatically simpler than App registration + webhook hosting and demos in seconds.
4. **`claude -p` headless mode is real and usable.** `claude --bare -p "..." --mcp-config tmp.json --allowedTools "Bash,Read" --output-format json` works. Caveat: the JSON output does not include a tool-call trace. Mitigation: instrument the local FastMCP server itself to log tool invocations to a file; the shadow agent's proof-of-invocation is that log entry, not stdout parsing.

#### Architecture (final)

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

#### Repo layout to set up (Hr 0)
| Repo | Purpose | Source |
|---|---|---|
| `<our-org>/plivo-python-stub` | Watched repo. Either a fork of `plivo/plivo-python` or a tiny stub with one fake resource to make the demo deterministic. | Fork or new |
| `<our-org>/plivo-mcp-fork` | Target repo for generated PRs. Fork of `plivo/mcp`. We add a `.github/workflows/auto-merge.yml` here. | Fork |
| `<our-org>/prmcp` | The agent itself: workflow + Python scripts + templates. | New |

#### `prmcp` repo file structure
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

#### Workflow yaml (sketch — what judges literally install)
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

#### Hour-by-hour build plan (24 hr, pair, both heavy Claude Code users)

| Hr | Person A | Person B | Riskiest? |
|----|----------|----------|---|
| 0–2 | Fork plivo-python + plivo/mcp into our org. Mint PAT, store as repo secret. | Get plivo/mcp's existing 6 tools running locally with FastMCP + `mcp inspector`. Capture baseline tool fixture. | No |
| 2–5 | Build `diff_sdk.py`: AST-walk `plivo/resources/*.py`, emit manifest JSON of `{resource, method, params, decorator_args}`. Snapshot-test against current SDK. | Build `synth_tool.py` + 5 Jinja templates (create/get/list/update/delete). Snapshot-test against existing `send_sms` / `make_call` for parity. | Yes — AST edge cases (decorators, dynamic methods, `@validate_args`). Mitigation: scope to the 5 canonical CRUD methods; flag everything else as `prmcp-unsupported` rather than guess. |
| 5–8 | Compose `diff_sdk → synth_tool` end-to-end. Hand-craft a fake "Transcripts" resource in our `plivo-python-stub`, verify pipeline emits the correct `@mcp.tool()` function. | Build `open_pr.py` with PyGithub. Open a real PR on our `plivo-mcp-fork` with the synthesized tool. Label it `prmcp-generated`. | No |
| 8–12 | Instrument the local FastMCP `server.py`: every tool invocation appends `{tool, args, ts, result}` to `/tmp/prmcp-trace.jsonl`. This is our proof-of-invocation. | Build `shadow_agent.py`: spin up the candidate `server.py` as a subprocess; write a temp `.mcp.json`; invoke `claude --bare -p "Use <tool> with these params: {...}" --mcp-config tmp.mcp.json --output-format json`; assert `/tmp/prmcp-trace.jsonl` has an entry for the new tool. | Yes — `claude -p` rate limits + headless config quirks. Mitigation: cache validation by `(resource, method)` signature; budget cap of 3 validation calls per PR. Backup: skip shadow agent, fall back to a unit-test smoke-import only — degraded but still demoable. |
| 12–15 | Compose the full workflow yaml. End-to-end live test: trigger by merging a staged PR on `plivo-python-stub`; watch Actions run; verify a PR opens on `plivo-mcp-fork`. | Wire CI on `plivo-mcp-fork`: smoke `python -c "import server"` + `pytest -k generated` on the synth'd tool. | No |
| 15–18 | Build `auto-merge.yml` on `plivo-mcp-fork`: when PR has both `agent-validated` label and green CI, squash-merge automatically. | Wire **intentional recovery beat**: shadow agent's first invocation injects a 429 (mock); agent retries with backoff; second call succeeds. Log both attempts to trace. This is the demo's "graceful recovery." | No |
| 18–21 | Stage the demo: prepare 2 candidate "new endpoint" PRs in `plivo-python-stub` (a `Transcripts.create` and a `Numbers.search`). Practice triggering each. Capture screen recordings as backup. | Polish README — copy-paste install block, GIF screencast, one-line "what PRMCP does," failure-mode docs. | No |
| 21–23 | Demo rehearsal #1 + #2 with stopwatch. Refine the talking script. | Final-pass `pytest` over all snapshot tests. Verify deterministic output. | No |
| 23–24 | Demo rehearsal #3. Backup video re-recorded if anything drifted. | Buffer. | No |

**Hard cutover at Hr 18** if shadow agent doesn't work end-to-end: drop shadow agent, ship the PR-opening pipeline with a smoke-import CI only. The demo loses the "Claude validated it" beat but keeps the "agent opens PR on agent's behalf" beat. Still wins the "By Agents" track.

#### Demo script (5 min total, target 3:30 spoken)

1. **(20s) Hook**: "`plivo/mcp` exposes 6 tools. The Plivo Python SDK has 60+ resources. The gap is human labor that doesn't scale. We built the agent that closes that gap automatically."
2. **(30s) Stage**: Show `plivo-python-stub` and `plivo-mcp-fork` side-by-side. Show current `server.py` has 6 `@mcp.tool()` functions.
3. **(45s) Trigger**: Merge a pre-staged PR on `plivo-python-stub` that adds `Transcripts.create()`. Actions tab pops; `PRMCP` workflow appears. Open it.
4. **(60s) Pipeline live**: Workflow log streams: `diff_sdk: 1 new resource detected (Transcripts.create)`. `synth_tool: emitted 1 new @mcp.tool() fn (28 lines)`. `shadow_agent: spawning FastMCP server...`. `claude -p invoked with new tool config`.
5. **(45s) Wow + recovery beat**: Shadow-agent log shows attempt 1 → 429 → backoff → attempt 2 → success. `/tmp/prmcp-trace.jsonl` displayed: confirmed tool invocation with real args. PR opens on `plivo-mcp-fork` with `agent-validated` label.
6. **(30s) Self-merge**: CI runs (smoke + snapshot). Green. Auto-merge action fires. `plivo-mcp-fork`'s `main` now has 7 tools, not 6. Run `mcp inspector` against it to prove the new tool is live.
7. **(20s) Install**: "Two lines of yaml + one PAT. Monday morning, paste this into `plivo/plivo-python` and `plivo/mcp` and the lag disappears forever."
8. (Buffer 30s for Q&A spillover.)

#### Risks & mitigations (refined)

| # | Risk | Likelihood | Mitigation |
|---|---|---|---|
| 1 | AST diffing misses non-canonical methods (e.g. `validateNumbers()` that doesn't fit CRUD) | Medium | Scope to the 5 canonical shapes; emit a `prmcp-unsupported` label on the PR for unknown shapes — judges *see* the agent reasoning about its own limits, which strengthens the pitch |
| 2 | Cannot install on real `plivo/plivo-python` mid-demo | Certain | Use our fork. Frame: "production-ready, awaiting maintainer adoption." Honest and lands well |
| 3 | `claude -p` rate-limited or flaky | Medium | Cache per `(resource, method)` signature. Hard cap at 3 validation invocations per PR. Fallback path is smoke-import CI |
| 4 | Shadow agent JSON output has no tool-call trace | Confirmed | Server-side instrumentation writes `/tmp/prmcp-trace.jsonl`; PRMCP parses *that*, not stdout |
| 5 | Actions runner can't reach localhost for FastMCP | Low | Both shadow agent + FastMCP server run on the same runner; use `127.0.0.1`. No external networking needed |
| 6 | PAT scope too broad → security pushback | Low | Use fine-grained PAT with write access only to `plivo-mcp-fork`. Document this clearly in README |
| 7 | `@validate_args` decorator parsing breaks on edge cases | Medium | Try decorator AST first; fall back to `inspect.signature` of the function source string; final fallback: skip params and mark `params: []` with `prmcp-incomplete-params` label |
| 8 | Genericity attack: "this is just OpenAPI-to-MCP codegen" | Low (we deflate it on stage) | We have NO OpenAPI input — we're doing AST → MCP, which is materially harder. Also: codegen tools don't *validate by running an LLM*, don't *open self-merging PRs*, and don't *operate as a long-lived watcher*. Three distinguishers, each demoed live |

#### Stack (all free, all verified)
- **Language**: Python 3.11 (matches `plivo/mcp` + `plivo-python`).
- **Libs**: `ast` (stdlib), `jinja2`, `PyGithub`, `fastmcp`, `plivo` SDK, `pytest`.
- **Codegen target**: `@mcp.tool()` decorated functions in `server.py` style.
- **Headless Claude**: `claude --bare -p ... --mcp-config ... --output-format json --allowedTools "Bash,Read"`. Burned against the user's existing Claude Code account.
- **Hosting**: Zero. Everything runs in GitHub Actions runners + the user's MacBook locally. No Cloudflare Tunnel needed (drop the original plan's tunnel — Actions makes it irrelevant).
- **Cost**: ₹0. Plivo trial creds optional (shadow agent doesn't need to actually call Plivo's API — it just needs to call the *new MCP tool*, which the FastMCP server can mock locally for the demo).

#### Why this still wins the "By Agents" track
- **Solves judges' own pain**: every Plivo engineer has shipped an SDK release and not updated `plivo/mcp`. The current 6-tool gap is *literally evidence of the bug PRMCP fixes*.
- **The agent is recursively visible**: Claude Code writes PRMCP, PRMCP runs Claude Code on the synth'd tool, the synth'd tool calls Plivo. Three nested agent loops, all on-screen.
- **Hard to copy**: a second team that also picks "PR automation for MCP" will not have AST-parsed `plivo-python` by Hr 5 — they'll have stalled on the missing OpenAPI spec like the first draft of this plan did.
- **"Monday morning shippable" is literal**: the PR can be opened against `plivo/plivo-python` and `plivo/mcp` on Monday with no further engineering — it's a workflow paste.

#### Verification (run before declaring done)
1. End-to-end happy path: merge staged PR on `plivo-python-stub` → within 90s, new PR opens on `plivo-mcp-fork` with the generated `@mcp.tool()` function for `Transcripts.create`.
2. Generated tool passes `python -c "from server import *"` (smoke import).
3. Generated tool passes a snapshot test in `tests/test_diff_synth.py`.
4. Shadow agent's `/tmp/prmcp-trace.jsonl` shows ≥1 entry naming the new tool, including the staged retry-after-429 recovery beat.
5. Auto-merge action fires on `agent-validated` label + green CI.
6. Whole demo end-to-end runs in ≤4:30 on a stopwatch with one practice. Backup screencast recorded.
7. README contains a copy-pasteable `prmcp.yml` and a 4-step install. A judge can install on their own fork in <60s.

---

### Idea D (backup): **Plivo Projects** — *Stripe-Projects-style agent provisioning for Plivo*
**One-line pitch**: A CLI + scoped-key issuer where an LLM agent runs `plivo agents init --budget=$10 --capabilities=sms,voice` and gets a sandboxed Plivo identity with hard spending caps, opt-in webhook URL, and a token rotation policy — no human in the loop.

- Kept on the bench because it's the boldest "For Agents" reframe, but **higher 24-hr execution risk** than A/B/C (auth surface area + needs Plivo backend access that hackathon teams may not have).
- Pursue only if Plivo internal team grants sandboxed-org access at kickoff.
- Otherwise pick A, B, or C.

---

## Step 5 — Self-Critique

| Concern | Idea(s) it hits | Fix applied |
|---|---|---|
| "Is there a simpler version that loses the magic?" | A | Yes — a non-concurrent single-call test runner. We defend the concurrency because the *grid* is the wow; without it, this is a regression test, not a demo. |
| "Is there a simpler version that loses the magic?" | B | Yes — a static error→fix lookup. We defend by including live retry + replay; without retry, judges see a docs table. |
| "Skeptical-judge attack: 'AgentDouble is just LLM evals'" | A | Counter: the calls are *real Plivo audio streams*, not transcript-level. Latency, drop, hand-off events are first-class. LLM evals can't measure those. |
| "Skeptical-judge attack: 'Doctor is just a docs lookup'" | B | Counter: live retry of the corrected call closes the loop. The judge sees the failed call → diagnosis → fixed call → success, in 90s. |
| "Skeptical-judge attack: 'PRMCP is just OpenAPI codegen'" | C | Counter: the shadow-agent validation step + GitHub App loop is the actual product. We surface that explicitly in the demo. |
| "Sneaking in paid dependencies?" | A | ElevenLabs has a free tier (10k chars/mo) — covers the demo. Backup is Plivo's built-in TTS, fully free. |
| "Sneaking in paid dependencies?" | B, C | None — Claude Code accounts provided, Plivo trial credits cover sandbox, GitHub App is free. |
| "Sneaking in hand-waved hard steps?" | A | Audio-stream synthetic caller is the risky bit — documented fallback (pre-rec WAV per turn) keeps the demo intact. |
| "Sneaking in hand-waved hard steps?" | B | CDR replay depth — scoped to headline triple + retry, deferring SIP state machine. |
| "Sneaking in hand-waved hard steps?" | C | Plivo public OpenAPI — use a controlled stub repo upstream for the demo; honest framing as "imagine this is the Plivo spec repo." |
| "Demo length feasibility" | A, B, C | All three rehearsed at 3 min; each leaves 2 min of slack inside the 5-min demo window for Q&A overflow or a second wow beat. |

---

## Top Recommendation (updated after PRMCP feasibility pass)

The choice is now a **B vs C tradeoff** rather than a single clear winner. The PRMCP feasibility pass removed two of its biggest unknowns (the GitHub App and the OpenAPI dependency both go away), which tightens its 24-hr execution profile substantially.

### Decision matrix

| Dimension | B — Doctor | C — PRMCP (expanded) |
|---|---|---|
| Track fit | For Agents | **By Agents (cleaner)** |
| Judges (Plivo eng) feel the pain? | Yes — every Plivo customer has | **Yes — every Plivo engineer has** (the 6-tool gap is the proof) |
| Demo guideline #4 (self-recovery) | Built into the product | Built into the shadow-agent step (staged 429 → backoff → success) |
| Demo wow | Solid (live retry-and-succeed) | **Higher — three nested agent loops visible on stage** |
| Execution risk @ 24hr | Lower | Moderate, with a clean fallback at Hr 18 |
| Genericity risk | Lower (positioning is sharp) | **Lower than before** — no other team has AST-parsed `plivo-python` by Hr 5 |
| "Monday morning shippable" | One-line MCP install | Two-line workflow paste — literally the same intervention applied at the eng-org level |
| Surprise factor for judges | Medium | **High — they will not expect a self-merging PR loop** |

### Recommendation

- **Default**: PRMCP (C). The "By Agents" track has fewer teams historically, the judges are exactly the population it serves, and the demo has the strongest narrative arc (agents writing agents writing agents). The feasibility-verified plan above has a Hr-18 hard cutover that protects the demo even if the shadow-agent step is flaky.
- **Pick B (Doctor) instead if**: at Hr 4 you don't have `diff_sdk.py` snapshot-passing on the existing `plivo-python` resources. That's the canary — if AST parsing is dragging, abandon C, do B. B's path has fewer unknowns and a cleaner degrade.
- **Pick A (AgentDouble) only if**: the Plivo organizers grant a sandbox vibe-agent endpoint at kickoff AND audio streaming latency tests cleanly by Hr 6.

---

## Verification (run this before declaring done)

The recommended default is PRMCP (C); its verification block lives inside Idea C's expanded section ("Verification (run before declaring done)") with 7 concrete acceptance gates.

If the team falls back to Doctor (B) at the Hr-4 canary:

1. `npx @plivo/doctor-mcp` boots locally on a clean Node 20 install. No env beyond `PLIVO_AUTH_ID` / `PLIVO_AUTH_TOKEN`.
2. A fresh Claude Code session with the MCP config added can:
   - Hit at least 5 distinct seeded error classes.
   - Recover automatically on at least 3 of them within a single agent turn.
   - Return a structured RCA on all 5.
3. CDR replay (if shipped) reconstructs the timeline for a known-failed call from a captured CDR fixture.
4. Demo runs end-to-end in under 3:30 with a stopwatch. Backup video recorded.
5. README has a copy-pasteable install block and a screencast GIF.
