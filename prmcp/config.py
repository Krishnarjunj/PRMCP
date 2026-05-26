"""prmcp.config — load prmcp.toml + .env, return a typed Config.

Single source of truth for runtime configuration. Every other module
takes a Config (or a sub-section of it) — no module reads os.environ
for SDK paths, repo names, or LLM settings of its own.

Lookup order:
1. cwd up to filesystem root for `prmcp.toml`
2. `.env` next to the discovered toml (also read from cwd as fallback)
3. environment variables (always allowed to override)

The `[sdk] source` value may be either a local filesystem path or a
GitHub `owner/repo` slug. If it doesn't resolve to an existing path,
the slug form is cloned into `.prmcp/sdk-source/` next to the toml.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

try:
    import tomllib  # py3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


CONFIG_FILENAME = "prmcp.toml"
ENV_FILENAME = ".env"
WORKSPACE_DIRNAME = ".prmcp"
SDK_CLONE_SUBDIR = "sdk-source"
SNAPSHOT_FILENAME = "sdk-snapshot.json"
CI_STATE_FILENAME = "ci-watcher.state"

_GITHUB_SLUG_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class SdkConfig:
    source: str
    resolved_path: Path
    resources_glob: str
    resource_base_classes: tuple[str, ...]
    client_path: str | None
    import_module: str
    client_expression: str
    exception_class: str


@dataclass(frozen=True)
class McpConfig:
    target_repo: str
    base_branch: str
    tool_dir: str


@dataclass(frozen=True)
class LlmConfig:
    model: str
    base_url: str | None


@dataclass(frozen=True)
class CiConfig:
    watched_repo: str | None
    workflow: str
    poll_interval_seconds: float


@dataclass(frozen=True)
class DaemonConfig:
    poll_interval_seconds: float
    debounce_seconds: float


@dataclass(frozen=True)
class PipelineConfig:
    trace_path: Path
    dry_run: bool
    snapshot_path: Path


@dataclass(frozen=True)
class Config:
    config_path: Path
    workspace: Path
    sdk: SdkConfig
    mcp: McpConfig
    llm: LlmConfig
    ci: CiConfig
    daemon: DaemonConfig
    pipeline: PipelineConfig
    secrets: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------- discovery


def find_config(start: Path | None = None) -> Path | None:
    cur = (start or Path.cwd()).resolve()
    for candidate in [cur, *cur.parents]:
        p = candidate / CONFIG_FILENAME
        if p.is_file():
            return p
    return None


def load_dotenv(path: Path) -> dict[str, str]:
    """Tiny .env parser. KEY=VALUE, comments, optional quotes."""
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        if key:
            out[key] = value
    return out


# ---------------------------------------------------------------- SDK resolve


def _looks_like_github_slug(value: str) -> bool:
    return bool(_GITHUB_SLUG_RE.match(value)) and not value.startswith((".", "/"))


def _clone_github_sdk(slug: str, dest: Path) -> Path:
    """Shallow-clone `slug` into `dest`. Returns dest path on success."""
    if dest.exists() and any(dest.iterdir()):
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://github.com/{slug}.git"
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", "--quiet", url, str(dest)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        detail = getattr(e, "stderr", "") or str(e)
        raise ConfigError(
            f"failed to clone SDK source {slug!r}: {detail.strip()}. "
            "Either set [sdk] source to a local path, or ensure `git` is on PATH."
        ) from e
    return dest


def resolve_sdk_source(source: str, workspace: Path) -> Path:
    candidate = Path(source).expanduser()
    if candidate.exists():
        return candidate.resolve()
    if _looks_like_github_slug(source):
        clone_dest = workspace / SDK_CLONE_SUBDIR
        return _clone_github_sdk(source, clone_dest).resolve()
    raise ConfigError(
        f"[sdk] source {source!r} is neither an existing path nor an "
        "`owner/repo` GitHub slug."
    )


# ---------------------------------------------------------------- main load


def _section(table: dict, name: str) -> dict:
    val = table.get(name, {})
    if not isinstance(val, dict):
        raise ConfigError(f"[{name}] must be a table in {CONFIG_FILENAME}")
    return val


def _require(table: dict, key: str, section: str) -> str:
    if key not in table or not str(table[key]).strip():
        raise ConfigError(f"missing required key [{section}].{key} in {CONFIG_FILENAME}")
    return str(table[key]).strip()


def load(
    *,
    cwd: Path | None = None,
    required_secrets: Iterable[str] = ("OPENAI_API_KEY", "PAT_TOKEN"),
) -> Config:
    cwd = (cwd or Path.cwd()).resolve()
    config_path = find_config(cwd)
    if config_path is None:
        raise ConfigError(
            f"no {CONFIG_FILENAME} found in {cwd} or any parent. "
            "Run `prmcp init` to create one."
        )
    project_root = config_path.parent
    raw = tomllib.loads(config_path.read_text())

    dotenv = load_dotenv(project_root / ENV_FILENAME)
    for k, v in dotenv.items():
        os.environ.setdefault(k, v)

    missing = [k for k in required_secrets if not os.environ.get(k)]
    if missing:
        raise ConfigError(
            "missing required secrets: "
            + ", ".join(missing)
            + f". Set them in {project_root / ENV_FILENAME} or the environment."
        )

    workspace = project_root / WORKSPACE_DIRNAME
    workspace.mkdir(parents=True, exist_ok=True)

    sdk_t = _section(raw, "sdk")
    mcp_t = _section(raw, "mcp")
    llm_t = _section(raw, "llm")
    ci_t = _section(raw, "ci")
    daemon_t = _section(raw, "daemon")
    pipeline_t = _section(raw, "pipeline")

    sdk_source = _require(sdk_t, "source", "sdk")
    sdk_path = resolve_sdk_source(sdk_source, workspace)

    sdk = SdkConfig(
        source=sdk_source,
        resolved_path=sdk_path,
        resources_glob=str(sdk_t.get("resources_glob", "**/resources/*.py")),
        resource_base_classes=tuple(sdk_t.get("resource_base_classes") or ()),
        client_path=(str(sdk_t["client_path"]) if sdk_t.get("client_path") else None),
        import_module=str(sdk_t.get("import_module", sdk_source.split("/")[-1])),
        client_expression=str(sdk_t.get("client_expression", "")),
        exception_class=str(sdk_t.get("exception_class", "Exception")),
    )

    mcp = McpConfig(
        target_repo=_require(mcp_t, "target_repo", "mcp"),
        base_branch=str(mcp_t.get("base_branch", "main")),
        tool_dir=str(mcp_t.get("tool_dir", "tools")),
    )

    llm = LlmConfig(
        model=str(llm_t.get("model", "gpt-4o-mini")),
        base_url=(str(llm_t["base_url"]) if llm_t.get("base_url") else None),
    )

    ci = CiConfig(
        watched_repo=(str(ci_t["watched_repo"]) if ci_t.get("watched_repo") else None),
        workflow=str(ci_t.get("workflow", "prmcp.yml")),
        poll_interval_seconds=float(ci_t.get("poll_interval_seconds", 30.0)),
    )

    daemon = DaemonConfig(
        poll_interval_seconds=float(daemon_t.get("poll_interval_seconds", 2.0)),
        debounce_seconds=float(daemon_t.get("debounce_seconds", 3.0)),
    )

    trace_path = Path(
        os.environ.get("PRMCP_TRACE_PATH")
        or pipeline_t.get("trace_path")
        or "/tmp/prmcp-trace.jsonl"
    ).expanduser()
    dry_run_env = os.environ.get("PRMCP_DRY_RUN")
    dry_run = (
        _truthy(dry_run_env)
        if dry_run_env is not None
        else bool(pipeline_t.get("dry_run", True))
    )
    snapshot_path = Path(
        pipeline_t.get("snapshot_path") or workspace / SNAPSHOT_FILENAME
    ).expanduser()

    pipeline = PipelineConfig(
        trace_path=trace_path,
        dry_run=dry_run,
        snapshot_path=snapshot_path,
    )

    secrets = {k: os.environ[k] for k in required_secrets if k in os.environ}

    return Config(
        config_path=config_path,
        workspace=workspace,
        sdk=sdk,
        mcp=mcp,
        llm=llm,
        ci=ci,
        daemon=daemon,
        pipeline=pipeline,
        secrets=secrets,
    )


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


__all__ = [
    "CONFIG_FILENAME",
    "ENV_FILENAME",
    "WORKSPACE_DIRNAME",
    "Config",
    "ConfigError",
    "SdkConfig",
    "McpConfig",
    "LlmConfig",
    "CiConfig",
    "DaemonConfig",
    "PipelineConfig",
    "find_config",
    "load",
    "load_dotenv",
    "resolve_sdk_source",
]


# Quiet unused-import nag without conditionally importing shutil — kept in case
# future helpers need it (e.g. clearing the workspace clone).
_ = shutil
