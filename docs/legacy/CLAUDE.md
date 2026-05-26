# Plivo Hackathon 2026 — Working Directory

## HARD RULE: commit messages

All commit messages MUST be 1 or 2 words. No exceptions. No body, no Co-Authored-By trailer, no scope prefixes — just 1 or 2 words.

This directory is the prep + working tree for the **Plivo Hackathon 2026**, a 24-hour internal hackathon. Use this file to ground Claude Code sessions running in this directory.

## Event facts

- **Theme**: "Plivo For Agents, Plivo By Agents"
- **Dates**: Fri 2026-05-22 3:00 PM → Sat 2026-05-23 3:00 PM build. Demos start Sat 3:00 PM. Winners 6:00 PM.
- **Format**: On-site at Plivo office, full-stay. Solo or pairs.
- **Prize**: ₹1,50,000 pool. Top 2 + 1 special prize.
- **Stack**: Claude Code / Cursor / Codex provided. Plivo accounts available. Repos go under the `plivo-hackathon-2026` GitHub org.
- **Judges**: Mike, Likith, Manish, Ayush (all Plivo engineers).
- **Demo**: 5 min live + 2 min Q&A.

## Demo guidelines the judges weighted (apply to every implementation choice)

1. One-line hook: what it does, who it's for.
2. One real Plivo pain point — make the judges nod.
3. Live agent demo end-to-end. Show the prompt, the tool calls, the result.
4. **Show one failure mode handled gracefully** — agent self-recovered without human in the loop (carrier error, retry, budget cap, etc.).
5. Shippability — install command, "Monday morning we can deploy this."

When generating code or reviewing changes for this hackathon, optimize for these criteria, not abstract code quality.

## This team

Pair, both heavy Claude Code users ("claudemaxxing"). Open on track. No fixed Plivo product depth. Win-first mindset.

## Track preference (decided)

**Primary: "Plivo By Agents"** with idea **PRMCP** (see `PRMCP.md`).
**Fallback at Hr-4 canary**: idea **Plivo Doctor MCP** (see `PLAN.md` — Idea B).

The Hr-4 canary is: if `diff_sdk.py` is not snapshot-passing on `plivo/plivo-python` resources by hour 4 of the build, abandon PRMCP and switch to Doctor.

## Files in this directory

- `HANDOFF.md` — **read first on session restart.** Current state of pipeline + demo-day extension (viz + daemon + launcher). Known sharp edges.
- `Context.md` — raw Slack export of the hackathon channel. Source of truth for event facts. Do not edit.
- `PLAN.md` — ideation audit (4 survivors, decision matrix). Background reference.
- `PRMCP.md` — PRMCP architecture + demo script. Background reference.
- `HARDENED.md` — original hour-by-hour build plan. Has stale references; cite HANDOFF.md first.
- `.env.example` — required env-var template for `prmcp-up`.
- `prmcp/` — pipeline Python package. `diff_sdk`, `synth_tool`, `shadow_agent`, `open_pr`, `run`, `daemon`, `cli`. `pip install -e prmcp` exposes console scripts `prmcp-up`, `prmcp-daemon`, `prmcp-run`.
- `viz/` — pipeline visualizer (Vite + React + React Flow). Vertical 6-stage workflow graph. Reads `/tmp/prmcp-trace.jsonl` via a Vite middleware at `viz/server/trace-api.ts`. Real runs in a LIVE section, four canonical demo runs in a DEMO section. Aesthetic: deep black + Plivo cobalt, Geist + Geist Mono. Standalone README at `viz/README.md`. **The build phase did NOT include this — added 2026-05-23 as a demo-prep extension.**
- `plivo-python-fork/` — local SDK checkout the daemon watches. Gitignored — see `prmcp-sdk-source-truth` memory.
- `Screenshot 2026-05-21 at 11.28.42 PM.png` / `Screenshot 2026-05-21 at 11.30.32 PM.png` — official poster images.

## One-line boot

```sh
prmcp/.venv/bin/prmcp-up
```

Spawns Vite (http://localhost:5173) + the SDK watcher daemon. Edit any file under `plivo-python-fork/plivo/resources/` → daemon catches the mtime change → debounces 3s → runs `prmcp.run` → trace line flows into the visualizer's LIVE section over SSE in ~200ms. Defaults `PRMCP_DRY_RUN=1`; flip in `.env` for live PR mode.

## Hard constraints to respect when writing code or proposing changes

- **No paid services.** Everything must run free at hackathon scale.
- **No external hosting.** GitHub Actions runners + the user's MacBook only. No Cloudflare Tunnel, no Vercel, no Render unless the idea explicitly needs it.
- **Python 3.11** for anything that ships into the `plivo/mcp` orbit (PRMCP, generated tools). `plivo/mcp` is FastMCP-based, single-file `server.py`, no tests, no CI.
- **No public Plivo OpenAPI spec exists.** Don't propose pipelines that depend on one. AST-parse `plivo/plivo-python` instead.
- **GitHub Actions + PAT > GitHub App** for the hackathon. App needs admin install + webhook hosting; Action is two lines of yaml.
- **Plivo trial creds optional.** Shadow agent flows can mock at the FastMCP server level for the demo.

## "Monday morning shippable" pattern

Every interface PRMCP (or Doctor, if we fall back) presents to a user should be one of:
- `npx <pkg>` (single-command install)
- A copy-pasteable workflow yaml + one secret
- A copy-pasteable MCP config block

If a feature requires more than that to install, cut it from the demo.

## Voice / opinions to keep

- Concrete > clever. Specific tool names, not abstractions.
- Terse responses. No trailing "summary" paragraphs.
- Don't add features beyond what the 24-hour scope needs. The hackathon scope is the canonical scope.
