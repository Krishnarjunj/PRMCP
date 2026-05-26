# prmcp

> Watch any Python SDK, auto-synthesize FastMCP tools for new resources, validate each generated tool with an LLM, and open a PR on the target MCP repo.

`prmcp` is a self-contained pipeline. Give it four things — an LLM API key, a GitHub PAT, the SDK repo to watch, and the MCP repo to PR into — and it handles everything else: AST-walking the SDK, diffing against a snapshot, rendering FastMCP tool wrappers, calling an LLM to validate them, and opening PRs.

---

## Install

```sh
pip install prmcp
```

Or from source:

```sh
git clone <this-repo>
cd <this-repo>
pip install -e .
```

Requirements: Python 3.11+, `git` on PATH (for cloning remote SDKs), and `gh` CLI on PATH if you enable the optional GitHub Actions watcher.

## Quickstart

In a fresh directory:

```sh
prmcp init
```

You'll be prompted for four values:

| Prompt | Example |
|---|---|
| OpenAI API key | `sk-…` |
| GitHub PAT (scopes: `repo`) | `ghp_…` |
| SDK source | a local path like `./my-sdk` **or** an `owner/repo` slug to clone |
| MCP target repo | `myorg/my-mcp` |

`prmcp init` writes:

- `prmcp.toml` — the project config (committed; see template below)
- `.env` — `OPENAI_API_KEY` + `PAT_TOKEN` (added to `.gitignore`)
- `.prmcp/` — workspace dir for the cloned SDK and the snapshot baseline (gitignored)

It auto-detects the resource directory and base classes by sampling the SDK, and lets you confirm or edit each value.

Once initialized:

```sh
prmcp up         # watcher in the foreground; Ctrl-C to stop
prmcp run        # one-shot pass
prmcp tail       # colored terminal view of the trace JSONL
```

The first `prmcp run` seeds `.prmcp/sdk-snapshot.json` as the baseline. Subsequent runs diff against it — any new `(resource, method)` pair triggers the render → validate → PR pipeline. `prmcp run --reseed` resets the baseline to the current SDK state.

## How it works

```
SDK source                                MCP target repo
   │                                          ▲
   │ file change                              │ PR opens
   ▼                                          │
prmcp.daemon  →  prmcp.run orchestrator       │
                   │                          │
                   ├─ diff_sdk     (AST walk)
                   ├─ synth_tool   (Jinja2 render)
                   ├─ shadow_agent (OpenAI function-calling: valid|invalid)
                   └─ open_pr      (PyGithub) ┘

                 every step → /tmp/prmcp-trace.jsonl
                              (tailed by `prmcp tail`)
```

## `prmcp.toml` reference

```toml
[sdk]
# Local path OR "owner/repo" GitHub slug (cloned into .prmcp/sdk-source/)
source = "stripe/stripe-python"

# Glob (relative to the resolved SDK root) for the resource modules
resources_glob = "stripe/api_resources/*.py"

# Class names that mark "this is a resource". Empty list ⇒ every public
# class with public methods is treated as a resource.
resource_base_classes = ["APIResource", "ListableAPIResource"]

# Python import name of the SDK package (used inside generated tools)
import_module = "stripe"

# The expression that builds a client inside each generated tool
client_expression = "stripe"

# Exception class to catch around each SDK call
exception_class = "stripe.error.StripeError"

# Optional: file inside the SDK whose Client.__init__ assigns each resource
# class to a `self.<attr>` — used to translate ClassName → client attribute.
# client_path = "stripe/stripe_client.py"

[mcp]
target_repo = "myorg/my-mcp"
base_branch = "main"
tool_dir    = "tools"

[llm]
model = "gpt-4o-mini"
# base_url = "https://api.openai.com/v1"   # set for OpenAI-compatible endpoints

[ci]
# watched_repo = "owner/repo"               # optional: enable the CI watcher
workflow = "prmcp.yml"
poll_interval_seconds = 30

[daemon]
poll_interval_seconds = 2.0
debounce_seconds      = 3.0

[pipeline]
trace_path = "/tmp/prmcp-trace.jsonl"
dry_run    = true
```

`dry_run = true` (default) prints the PR that *would* be opened without touching GitHub. Flip to `false` when you're ready for live PRs.

## Console scripts

| Command | What it does |
|---|---|
| `prmcp init` | Interactive bootstrap of `prmcp.toml` + `.env`. Auto-detects SDK conventions. |
| `prmcp up` | Daemon + (optional) CI watcher in one process. Ctrl-C tears all down. |
| `prmcp run` | Single pipeline pass. `--reseed` resets the snapshot baseline. |
| `prmcp daemon` | SDK file watcher only. |
| `prmcp ci-watcher` | GitHub-Actions → local-trace bridge only. Requires `[ci] watched_repo`. |
| `prmcp tail` | Real-time terminal view of the trace JSONL. ANSI-colored, groups runs by 30s gaps. |

## Environment variables

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | Required. Used by the shadow validator. |
| `PAT_TOKEN` | Required for live PR mode. Personal access token with `repo` scope. |
| `PRMCP_DRY_RUN` | Overrides `[pipeline] dry_run` (`1`/`0`). |
| `PRMCP_TRACE_PATH` | Overrides `[pipeline] trace_path`. |
| `PRMCP_LOG_LEVEL` | Python `logging` level (default `INFO`). |
| `PRMCP_INJECT_429` | `1` → simulate a single 429 from the LLM to exercise the retry path. |

## Layout

```
your-project/
├── prmcp.toml          # config, committed
├── .env                # secrets, gitignored
└── .prmcp/             # gitignored
    ├── sdk-source/     # cloned SDK (if `source` was a GitHub slug)
    ├── sdk-snapshot.json
    └── ci-watcher.state
```

## License

MIT.
