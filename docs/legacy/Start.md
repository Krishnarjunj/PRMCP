# Start.md — PRMCP Hackathon Runbook

> The execution-order companion to `HARDENED.md`. Read HARDENED.md once tonight for the *what* and *why*. This file is the *what to do, when, in what order* — designed to be the only doc you re-read during the 24-hour build. Reference HARDENED.md §N for details when this file points there.

---

## 0. Pre-flight tonight (≤10 min, before you sleep)

Hard prerequisites — if any of these aren't done when your head hits the pillow, you start tomorrow 30 min behind.

| # | Action | Verification |
|---|--------|--------------|
| 1 | Mint Gemini API key at https://aistudio.google.com/app/apikey | You have an `AIza...` string copied somewhere you'll find tomorrow |
| 2 | Mint classic PAT at https://github.com/settings/tokens (Generate new → classic). Scope: `public_repo` only. Label: `PRMCP-2026`. | You have a `ghp_...` string copied somewhere you'll find tomorrow |
| 3 | Confirm both forks visible: `gh repo view <you>/plivo-python` and `gh repo view <you>/mcp` | Both return repo metadata, not 404 |
| 4 | Laptops charged, chargers in bag, phone alarms set for sync times (see §3) | — |
| 5 | Skim HARDENED.md §1 + §3 + §5 once more so the shape is fresh | — |
| 6 | Pair-decide roles: **Person A = SDK/AST side**, **Person B = MCP/validation side** (lock this; switching mid-build kills momentum) | Both pair members know which they are |
| 7 | Sleep 7-8 hrs. No coding tonight. | — |

Do NOT do tonight:
- Don't `gh repo fork` if you've already forked. Forks are done.
- Don't start writing `diff_sdk.py` or any code. The plan needs you sharp at Hr 0.
- Don't read `Context.md` / `PLAN.md` for the third time. You know the plan.

---

## 1. Friday 14:30 IST (T-30) — Arrive at venue

| # | Action |
|---|--------|
| 1 | Find power outlet. Plug in both laptops. |
| 2 | Connect to venue Wi-Fi. Run `curl -s https://api.github.com/zen` — non-empty response = network healthy. |
| 3 | Open terminal on each laptop. `cd /Users/krishnarjun.j/Krish/hackathon` (Person A) and equivalent on Person B's machine. |
| 4 | Open `HARDENED.md` and `Start.md` in a markdown viewer or editor that stays visible. |
| 5 | Set phone alarms: **17:00 (Hr-4 canary)**, **20:00 (Hr 5 sync)**, **23:00 (Hr 8 sync)**, **03:00 (Hr 12 sync)**, **08:00 (Hr 17 GO/NO-GO)**, **14:45 (T-15 rehearsal)**. |
| 6 | Verify both keys (Gemini + PAT) are accessible (e.g., in a password manager or temp doc you can both see). |
| 7 | Snacks + water within reach. You won't move much in the next 24h. |

---

## 2. Friday 15:00 IST (Hr 0) — Build starts

### 2.1 Open Claude Code (both pair members, each on own machine)

```bash
cd /Users/krishnarjun.j/Krish/hackathon
claude
```

In the new session, type:

```
/clear
```

**Why /clear**: this wipes the current session's conversation history. CLAUDE.md, your memory directory, and all working-directory files are still loaded automatically — you keep all the persistent context. /clear just gives you a fresh conversation pointer so the model isn't anchoring on stale chat history from the planning session.

Then, as your first message in the cleared session, paste this prompt verbatim (adjust A/B to your role):

```
Hackathon Hr 0. I'm Person A (SDK/AST side). Read HARDENED.md fully, then HARDENED.md §3 row "0–2" for my immediate tasks. Use TodoWrite to track the Hr 0–2 sub-steps. Begin with mint-PAT-and-secrets work; ask me only if you hit a blocker.

Hard constraints:
- Source of truth is HARDENED.md (not PRMCP.md or PLAN.md — those are background).
- Commit + push every 30 min.
- /clear is NOT to be used inside this 2-hour window — context continuity matters.
- If HARDENED.md and reality contradict (a flag changed, a package moved), flag it to me before improvising.
```

Person B uses the same prompt with `Person B (MCP/validation side)` substituted.

### 2.2 Hr 0–2 split

| Time | Person A (SDK/AST) | Person B (MCP/validation) |
|------|-------------------|---------------------------|
| 15:00–15:30 | Run HARDENED.md §4 SETUP block verbatim (sections labelled "ON DEV LAPTOP" + "Load secrets"). Set both repo secrets, set `MCP_REPO` variable. | Clone `<you>/mcp` locally. `pip install fastmcp plivo`. `python server.py &` — confirm 6 tools register. |
| 15:30–16:00 | Bootstrap `prmcp/` directory per HARDENED.md §4 (`git init prmcp`, `requirements.txt`, venv). First commit + push. | `npx --yes @modelcontextprotocol/inspector` against local `server.py`. Screenshot the tool list — this is your baseline fixture. Save to `fixtures/baseline_inspector.png`. |
| 16:00–16:30 | Smoke-test Gemini: `python -c "from google import genai; print(genai.Client().models.generate_content(model='gemini-2.5-flash', contents='hi').text)"`. Must return text in <5s. If it fails, debug NOW — this is load-bearing. | Capture one `@mcp.tool()` function's signature as a JSON file. This becomes the "expected output" baseline for synth tests. |
| 16:30–17:00 | Stub the `prmcp/src/prmcp/` package layout: empty `diff_sdk.py`, `synth_tool.py`, `shadow_agent.py`, `open_pr.py`, `templates/`, `tests/`. Commit. | Convert one tool schema → Gemini `FunctionDeclaration` by hand. Validate Gemini accepts it. This proves the shim path before A/B sync at Hr 2. |

### 2.3 Hr 2 sync (17:00 IST)

3-min stand-up between pair (voice or quick desk visit):
- Person A reports: PAT works (test: can you `gh pr list -R <you>/mcp`?); Gemini auth works; prmcp scaffold pushed.
- Person B reports: local FastMCP runs; inspector connects; Gemini function-call shim proven on one tool.
- Both say YES → proceed to Hr 2–5 block.
- Either says NO → fix the gap first; do not start AST work on a broken foundation.

---

## 3. Hr 2–5 (17:00–20:00) — Build the riskiest pieces

| Time | Person A | Person B |
|------|----------|----------|
| 17:00–18:00 | Write `diff_sdk.py`: AST-walk `<fork>/plivo-python/plivo/resources/*.py`. Emit `manifest.json` of `{resource, method, params, decorator_args}` per HARDENED.md §3 row "2–5". Three shape detectors: standard pair / singleton interface / sub-resource. Skip-list: `nodes.py`, `numberpools.py`. | Write `synth_tool.py` + the 5 Jinja templates (`tool_create.py.jinja` etc.) + 1 passthrough template. Each template emits a `@mcp.tool()` function wrapping `plivo.RestClient().X.Y(...)`. |
| 18:00–19:00 | Write `tests/test_diff_sdk.py`: feed the current `plivo-python/resources/` tree, assert manifest contains the 16 clean-CRUD files. Snapshot the output. | Write `tests/test_synth.py`: feed `Transcripts.create` fixture → assert output matches expected `@mcp.tool()` Python source byte-for-byte. |
| 19:00–20:00 | Iterate on AST until snapshot passes. Commit + push frequently. | Iterate on Jinja until snapshot passes. Commit + push frequently. |

### 3.1 Hr-4 canary (CRITICAL — 19:00 IST)

**This is a hard gate. No negotiation.**

```bash
cd prmcp
source .venv/bin/activate
pytest tests/test_diff_sdk.py -v
```

- **All 16 clean-CRUD files snapshot-pass** → continue PRMCP path. Tell Person B "canary green, full speed."
- **Any failure that can't be fixed in <30 min** → STOP. Switch to Plivo Doctor (`PLAN.md` §Idea B). Person A scraps `diff_sdk.py`, Person B keeps the FastMCP infrastructure (Doctor reuses it). You lose ~4 hrs of work but Doctor has a flatter risk profile and B's work survives.

If you flip to Doctor: open a new Claude Code session (`/clear`, then `cat PLAN.md` and ask the model to ground in §Idea B), and restart the runbook from a Doctor-shaped Hr-4 (skip ahead in PLAN.md §Idea B's build plan).

### 3.2 Hr 5 sync (20:00 IST)

| Check | Pass condition |
|-------|---------------|
| `diff_sdk.py` snapshot test green? | Yes |
| `synth_tool.py` snapshot test green for `Transcripts.create`? | Yes |
| Both committed and pushed? | Yes |
| Demo PR target = `<you>/mcp:main` (your fork), not `plivo/mcp:main`? | Hardcoded in `open_pr.py` skeleton |

If all yes → eat something, drink water, proceed.

---

## 4. Hr 5–8 (20:00–23:00) — Compose the pipeline

| Time | Person A | Person B |
|------|----------|----------|
| 20:00–21:00 | Compose `diff_sdk → synth_tool` E2E. Hand-craft a fake `Transcripts.create` Python file in `<you>/plivo-python/plivo/resources/transcripts.py` (don't push to GitHub yet — local only). Run the pipeline; verify it emits the expected `@mcp.tool()` function. | Write `open_pr.py`: PyGithub 2.9.1, classic PAT via `Auth.Token(os.environ["PAT_TOKEN"])`. **Critical safety**: add `assert not target.startswith("plivo/")` at the top — refuse to PR to upstream. |
| 21:00–22:00 | Add fixtures: `fixtures/sample_new_resource.py` (the Transcripts file) + `fixtures/expected_tool.py` (what synth should produce). Add to test suite. | Test `open_pr.py` against `<you>/mcp` with a hand-crafted patch. Open the PR. Verify the `prmcp-generated` label gets applied. **Close the PR after testing** — don't pollute. |
| 22:00–23:00 | Catch up on any debt from Hr 2–5. Refactor for clarity (Claude Code will help). | Write `src/prmcp/run.py` — the entrypoint that wires `diff_sdk → synth_tool → open_pr`. Skip the validation step for now. |

### Hr 8 sync (23:00 IST)

- E2E dry run (local, no Actions yet): `python -m prmcp.run --target <you>/mcp --watched-dir <you>/plivo-python`.
- Expected: a PR opens on `<you>/mcp` with the synthesized `transcripts_create` tool. Close it.
- If the dry run works → you're well ahead of schedule. Take a 15-min break.

---

## 5. Hr 8–12 (23:00–03:00) — The validation loop (riskiest block)

| Time | Person A | Person B |
|------|----------|----------|
| 23:00–00:00 | Instrument FastMCP `server.py` (the one in `<you>/mcp`): add a tiny wrapper that appends `{tool, args, ts, status, result}` to `$PRMCP_TRACE_PATH` (default `./prmcp-trace.jsonl`). Module-level counter pattern for the 429 injection (HARDENED.md §6 risk #1 / red-team fix details). | Write `shadow_agent.py`: spawn FastMCP `server.py` as a subprocess via `asyncio.create_subprocess_exec`, connect an MCP client (or simpler: load the tool function directly), call Gemini with the synthesized tool as a `FunctionDeclaration`, parse the function_call response, invoke the tool, log to trace. |
| 00:00–01:00 | Wire the 429 injection: when `PRMCP_INJECT_429=1` AND module-counter == 1 (first call), raise `RuntimeError("rate_limited_429")`; second call passes through. Append both attempts to trace. | Wire the Gemini function-calling shim: 10-line MCP-schema → `FunctionDeclaration` converter. Cache validation by `(resource, method)` signature with a JSON cache file. Hard cap 3 Gemini calls per PR. |
| 01:00–02:00 | Compose `run.py` with the new validation step: `diff_sdk → synth_tool → spawn server with new tool → shadow_agent → assert trace has [429, 200] → open_pr`. | Help Person A debug the composition. Run end-to-end locally with `PRMCP_INJECT_429=1`. |
| 02:00–03:00 | Iterate until trace.jsonl reliably contains 2 lines (status 429, status 200) on every clean run. **This is the demo's wow beat — it must be deterministic.** | Same. Aim for 10/10 clean runs in a row. |

### Hr 12 sync (03:00 IST)

- Run the full local pipeline 5 times. All 5 must produce trace.jsonl with exactly `[status:429, status:200]`.
- Both committed + pushed.
- You're now past the riskiest hour-block. If you're here on schedule, the rest is mostly integration work.

---

## 6. Hr 12–15 (03:00–06:00) — GitHub Actions integration

| Time | Person A | Person B |
|------|----------|----------|
| 03:00–04:00 | Write `.github/workflows/prmcp.yml` per HARDENED.md §4. `cache: 'pip'`, `GH_TOKEN` env, `PRMCP_TRACE_PATH=${{ github.workspace }}/prmcp-trace.jsonl`, `actions/upload-artifact@v4` step. | Set up `.github/workflows/ci.yml` on `<you>/mcp`: smoke `python -c "from server import *"` + snapshot test that any new `@mcp.tool()` function imports cleanly. |
| 04:00–05:00 | Push prmcp to `<you>/prmcp` GitHub repo (new). Workflow yaml references `pip install git+https://github.com/<you>/prmcp.git@main`. Trigger first real Actions run via `workflow_dispatch`. Watch it; fix any auth/path issues. | Sketch the `auto-merge.yml` for `<you>/mcp` using `pascalgn/automerge-action@v0.16.4` (HARDENED.md §4). Test by labelling a hand-crafted PR `agent-validated` and watching it merge. |
| 05:00–06:00 | First real E2E test: merge a staged PR on `<you>/plivo-python` adding `Transcripts.create` → watch PRMCP workflow run → verify PR appears on `<you>/mcp` → verify auto-merge fires. **This is your first full demo dry-run.** | Help A debug. Capture screen recording of the first successful E2E run — this becomes the backup screencast (HARDENED.md §5 fallback). |

### Hr 15 sync (06:00 IST)

- First successful E2E happened? Backup screencast captured?
- Both YES → eat real food, take a 20-min break. You're past the major work.

---

## 7. Hr 15–18 (06:00–09:00) — Polish + recovery beat + Hr-17 gate

| Time | Person A | Person B |
|------|----------|----------|
| 06:00–07:00 | Tune the workflow: remove any unnecessary steps, verify ≤90s total wall-time on warm cache. | Polish the recovery beat: trace.jsonl must show `[status:429, ..., status:200, ...]` in a way that's visually obvious on stage. Format the JSON lines for readability. |
| 07:00–08:00 | Stage demo PR #1 (`Transcripts.create`) on `<you>/plivo-python`. Mark as draft. | Stage demo PR #2 (`Numbers.search`) on `<you>/plivo-python`. Mark as draft. Backup option for the demo if PR #1 misbehaves. |
| 08:00–09:00 | **Hr-17 GO/NO-GO check** — see §7.1 below. | Same — both run this together. |

### 7.1 Hr 17 GO/NO-GO (08:00 IST) — CRITICAL GATE

Run the full pipeline **3 consecutive times from a clean checkout** (delete the prmcp/.venv and reinstall each time to simulate the runner's cold-start):

```bash
for i in 1 2 3; do
  echo "=== Run $i ==="
  rm -rf prmcp/.venv
  cd prmcp && python3.11 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
  time python -m prmcp.run --target <you>/mcp --watched-dir <you>/plivo-python
  echo "--- trace.jsonl ---"
  cat prmcp-trace.jsonl
  deactivate
  cd ..
done
```

All 3 runs must pass:
- **(a)** PR opens within 90s (wall-time from script start to `gh pr view` succeeding)
- **(b)** `prmcp-trace.jsonl` has **exactly 2 lines**: line 1 with `"status":429`, line 2 with `"status":200`
- **(c)** Total wall-time ≤90s warm cache

**Decision tree**:
- All 3 runs pass all 3 checks → **GREEN. Keep full demo with shadow-agent validation.**
- Any single check fails in any single run → **AMBER. Re-run once more.** If amber persists → **RED.**
- **RED → drop shadow-agent step. Ship smoke-import CI only.** Demo loses "Gemini validated it" beat, keeps "agent opens PR + auto-merges" beat. Reframe pitch: "validation is a stretch goal — the load-bearing claim is automated PR + merge." Still wins "By Agents" track.

Do not push through a flaky pipeline. A failed checkpoint on stage is worse than a smaller demo that runs clean.

---

## 8. Hr 18–21 (09:00–12:00) — Staging + README

| Time | Person A | Person B |
|------|----------|----------|
| 09:00–10:00 | Prepare both staged demo PRs to be perfectly mergeable. Test the demo flow end-to-end from "click Merge" to "auto-merge succeeds." Time it. | Write README.md for `<you>/prmcp`: copy-paste install (the 2 yaml files + secrets), a screencast GIF (extracted from the backup recording), one-line "what PRMCP does," failure-mode docs. |
| 10:00–11:00 | Record fresh backup screencast (90 sec, full pipeline + closing inspector beat). Save as MP4 in `~/Desktop/PRMCP-backup.mp4`. | Pre-stage clipboard on the judge laptop with the install command. Pre-warm `npx @modelcontextprotocol/inspector` cache. |
| 11:00–12:00 | Rehearsal #1 — full 5-min demo with stopwatch. Use HARDENED.md §5 script verbatim. Note any beats that ran long. | Be the "judge" for rehearsal #1. Note any beats that were unclear. |

---

## 9. Hr 21–24 (12:00–15:00) — Rehearse, eat, rest

| Time | Person A | Person B |
|------|----------|----------|
| 12:00–13:00 | Rehearsal #2. Adjust pacing based on rehearsal #1 notes. | Be the "judge" again. |
| 13:00–14:00 | Eat lunch. Stretch. Walk for 10 min. You've been at this for 22 hours. | Same. |
| 14:00–14:30 | Rehearsal #3 — fully dressed (this is the dry-run). | Same. |
| 14:30–14:45 | Final GO/NO-GO checklist run-through (HARDENED.md §8). 12 items, ≤30s each. | Same. |
| 14:45–15:00 | **T-15**: pre-warm one workflow run via `gh workflow run prmcp.yml -R <you>/plivo-python` (per HARDENED.md §6 risk #4 mitigation). Open browser tabs: Actions tab on `<you>/plivo-python`, PR list on `<you>/mcp`, inspector UI. | Same — Person B watches the pre-warm run; if it fails, you have 15 min to recover. |

---

## 10. Saturday 15:00 IST — DEMO

Follow HARDENED.md §5 verbatim. Don't deviate. Don't ad-lib unless a CHECKPOINT fires.

If anything goes wrong:
- CHECKPOINT 3 fails (Actions tab silent): `gh workflow run prmcp.yml` from terminal, frame as "manual trigger because some teams will want this too."
- CHECKPOINT 4 fails (`diff_sdk` silent): cut to backup screencast, narrate over it.
- CHECKPOINT 5 fails (trace missing or 1 line): `gh run download -n prmcp-trace` in side terminal, narrate as "fetching from the artifact store — this is how teams debug after the fact." Reframes failure as feature.
- CHECKPOINT 6 fails (PR didn't open): `gh pr create` manually, frame as "demonstrating the merge half independently."

After demo, regardless of result: shake hands, accept questions, drink water. Final winners announced at 18:00.

---

## 11. Claudemaxxing tips for the 24h

These are general operating principles for both of you.

| Tip | Why |
|-----|-----|
| Use TodoWrite/TaskCreate at the start of each hour-block to enumerate concrete sub-steps | Forces decomposition; gives Claude visible state to track |
| `/clear` ONLY between major phases (Hr 0→2, Hr 12→15, Hr 17→18) and ONLY if context feels stale | Context continuity is your friend during integration work |
| Spawn Explore subagents for "where does X live in this codebase" questions | Protects your main thread from getting clogged with file reads |
| Spawn Plan subagents for non-trivial design decisions (e.g., "how do I shim MCP schema → Gemini FunctionDeclaration cleanly?") | Forces structured thinking; saves tokens |
| Commit every 30 min. Push every hour. | A power outage at Hr 14 cannot cost you more than 30 min |
| If you're stuck for 15+ min on the same bug, /clear and re-explain with fresh context. | Loop-breaks the model's stale framing |
| Speak the constraint aloud before asking. "I need X without using Y because Z" — pair member or Claude responds better to constraints than open questions. | — |
| At every sync point, force a 2-min status delta between A and B. | Catches drift before it compounds |
| When in doubt: HARDENED.md §3 is the plan. HARDENED.md §9 is the fallback tree. | Single source of truth |

---

## 12. The "do not" list

Things that will lose you time if you do them. Bookmark this list.

- ❌ Don't refactor anything that already works. The hackathon scope is the canonical scope.
- ❌ Don't try to make `diff_sdk.py` handle the full Plivo SDK. 16 clean-CRUD files is the scope (HARDENED.md C3.2).
- ❌ Don't open PRs against upstream `plivo/*`. The guardrail in `open_pr.py` should make this impossible; double-check anyway.
- ❌ Don't use fine-grained PATs. Classic PAT only (HARDENED.md C4.5).
- ❌ Don't put the trace file in `/tmp` or `$RUNNER_TEMP`. Always `$GITHUB_WORKSPACE/prmcp-trace.jsonl` (HARDENED.md red-team fix #3).
- ❌ Don't add the Claude CLI to the runner. Validation is Gemini-only on CI. Claude Code stays on the dev laptop for building, not validating.
- ❌ Don't skip the Hr-4 canary. If `diff_sdk.py` isn't snapshot-passing at Hr 4, switching to Doctor is the right call, not a defeat.
- ❌ Don't skip the Hr-17 GO/NO-GO. A flaky pipeline that fails on stage is worse than a smaller demo that runs clean.
- ❌ Don't demo without the backup screencast in your back pocket.
- ❌ Don't drink more than 3 cups of coffee. You will be jittery and slow.

---

## 13. Files you'll touch (cheat sheet)

```
/Users/krishnarjun.j/Krish/hackathon/
├── CLAUDE.md              # Project constraints — read once at Hr 0, then forget
├── HARDENED.md            # Source of truth — reference as needed
├── PRMCP.md               # Background — don't re-read during build
├── PLAN.md                # Doctor fallback — only open if Hr-4 canary fires
├── Start.md               # THIS FILE — the runbook you live in
├── prmcp/                 # NEW — created at Hr 0
│   ├── src/prmcp/
│   │   ├── diff_sdk.py    # Hr 2–5, Person A
│   │   ├── synth_tool.py  # Hr 2–5, Person B
│   │   ├── shadow_agent.py# Hr 8–12, Person B
│   │   ├── open_pr.py     # Hr 5–8, Person B
│   │   ├── run.py         # Hr 5–8, Person A (entrypoint)
│   │   └── templates/     # 5 CRUD .jinja + 1 passthrough.jinja
│   ├── fixtures/
│   ├── tests/
│   ├── requirements.txt
│   └── README.md          # Hr 18–21, Person B
├── <fork>/plivo-python/   # Local clone of your fork (watched repo)
│   └── .github/workflows/prmcp.yml   # Hr 12–15, Person A
└── <fork>/mcp/            # Local clone of your fork (target repo)
    └── .github/workflows/auto-merge.yml + ci.yml  # Hr 12–15, Person B
```

---

## 14. One-line summary you can repeat to yourself at 3 AM

> "AST-diff the SDK, synth a tool, validate with Gemini, open a PR on the fork, auto-merge on green. 16 clean-CRUD files in scope. Trace file at $GITHUB_WORKSPACE. Hr-4 canary, Hr-17 GO/NO-GO, demo at Sat 3 PM."

If you forget everything else, that sentence regenerates the plan.

Good luck. See you at Hr 0.
