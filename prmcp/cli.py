"""prmcp.cli — entrypoints for `pip install prmcp`.

Console scripts (declared in pyproject.toml):

    prmcp              # umbrella: prmcp <init|up|run|daemon|ci-watcher|tail>
    prmcp-up           # daemon + ci_watcher in one process
    prmcp-run          # one-shot pipeline pass
    prmcp-daemon       # SDK watcher only
    prmcp-ci-watcher   # GitHub-Actions → local-trace bridge only
    prmcp-tail         # terminal live tail of the trace JSONL
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import signal
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable

from prmcp import config as _config
from prmcp import ui


_GITHUB_SLUG_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


# ----------------------------------------------------------------- init


_RESOURCE_DIR_NAMES = ("resources", "api_resources")
_RESOURCE_FILE_SUFFIXES = ("_service.py", "_resource.py", "_resources.py")
_TEST_PATH_TOKENS = {"test", "tests", "testing", "spec", "specs"}


def _is_test_path(rel: Path) -> bool:
    return any(part.lower() in _TEST_PATH_TOKENS for part in rel.parts)


def _detect_resources_glob(sdk_path: Path) -> str | None:
    """Pick the glob that yields the most resource-looking .py files.

    Tries, in order:
      1. Any directory literally named `resources/` or `api_resources/`.
      2. Files matching `_*_service.py` / `*_service.py` / `*_resource.py`.

    Returns a glob string relative to `sdk_path`, or None.
    """
    candidates: list[tuple[int, str]] = []
    for name in _RESOURCE_DIR_NAMES:
        for dirpath in sdk_path.rglob(name):
            if not dirpath.is_dir():
                continue
            if _is_test_path(dirpath.relative_to(sdk_path)):
                continue
            count = sum(1 for p in dirpath.glob("*.py") if p.stem != "__init__")
            if count:
                rel = dirpath.relative_to(sdk_path)
                candidates.append((count, f"{rel.as_posix()}/*.py"))
    if candidates:
        candidates.sort(reverse=True)
        return candidates[0][1]

    for suffix in _RESOURCE_FILE_SUFFIXES:
        suffix_globs = [f"**/*{suffix}", f"**/_*{suffix}"]
        for g in suffix_globs:
            hits = [
                p for p in sdk_path.glob(g)
                if p.is_file() and not _is_test_path(p.relative_to(sdk_path))
            ]
            if not hits:
                continue
            common = _shared_parent(hits)
            if common is None:
                continue
            rel = common.relative_to(sdk_path)
            pattern = f"_*{suffix}" if g.startswith("**/_") else f"*{suffix}"
            return f"{rel.as_posix()}/{pattern}" if rel.parts else pattern
    return None


def _shared_parent(paths: list[Path]) -> Path | None:
    if not paths:
        return None
    parents = [p.parent for p in paths]
    common = parents[0]
    for parent in parents[1:]:
        try:
            common = Path(os.path.commonpath([common, parent]))
        except ValueError:
            return None
    return common


def _detect_base_classes(sdk_path: Path, glob: str) -> list[str]:
    counter: Counter[str] = Counter()
    samples = 0
    for p in sdk_path.glob(glob):
        if samples >= 8:
            break
        if not p.is_file():
            continue
        samples += 1
        try:
            tree = ast.parse(p.read_text())
        except (OSError, SyntaxError):
            continue
        for node in tree.body:
            if not isinstance(node, ast.ClassDef) or node.name.startswith("_"):
                continue
            for b in node.bases:
                if isinstance(b, ast.Name):
                    counter[b.id] += 1
                elif isinstance(b, ast.Attribute):
                    counter[b.attr] += 1
    return [name for name, _count in counter.most_common(3)]


def _detect_import_module(sdk_path: Path, slug_fallback: str) -> str:
    """Best guess at the user-facing import name.

    1. If the SDK ships a top-level `<name>/__init__.py`, prefer `<name>`.
    2. Otherwise normalize `slug_fallback` by dropping `python-` /
       `-python` affixes and converting dashes to underscores.
    """
    for child in sdk_path.iterdir():
        if child.is_dir() and (child / "__init__.py").is_file() and not child.name.startswith("."):
            if child.name not in {"tests", "test", "examples", "docs"}:
                return child.name
    name = slug_fallback
    if name.startswith("python-"):
        name = name[len("python-"):]
    if name.endswith("-python"):
        name = name[: -len("-python")]
    return name.replace("-", "_")


def _write_gitignore(project_root: Path) -> bool:
    target = project_root / ".gitignore"
    needed = [".env", f"{_config.WORKSPACE_DIRNAME}/"]
    existing = target.read_text().splitlines() if target.is_file() else []
    additions = [n for n in needed if n not in existing]
    if not additions:
        return False
    with target.open("a", encoding="utf-8") as fh:
        if existing and existing[-1].strip():
            fh.write("\n")
        fh.write("# prmcp\n")
        for line in additions:
            fh.write(line + "\n")
    return True


def init(argv: Iterable[str] | None = None) -> int:
    """`prmcp init` — interactive bootstrap of prmcp.toml + .env."""
    parser = argparse.ArgumentParser(prog="prmcp init")
    parser.add_argument("--openai-key", default=None)
    parser.add_argument("--pat", default=None)
    parser.add_argument("--sdk-repo", default=None,
                        help="local path or owner/repo")
    parser.add_argument("--mcp-repo", default=None, help="owner/repo")
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--force", action="store_true",
                        help="overwrite existing prmcp.toml / .env")
    args = parser.parse_args(list(argv) if argv is not None else sys.argv[1:])

    project_root = Path.cwd()
    toml_path = project_root / _config.CONFIG_FILENAME
    env_path = project_root / _config.ENV_FILENAME

    interactive = ui.is_tty()

    ui.logo()
    ui.banner(
        "prmcp · init",
        [
            ("project", str(project_root)),
            ("config",  str(toml_path)),
            ("env",     str(env_path)),
        ],
    )

    if toml_path.exists() and not args.force:
        ui.fail(f"{toml_path.name} already exists. Re-run with [kbd]--force[/kbd] to overwrite.")
        return 2

    def _need(value: str | None, label: str, default: str | None = None,
              password: bool = False) -> str:
        if value:
            return value
        if interactive:
            return ui.prompt(label, default=default, password=password)
        if default is not None:
            return default
        ui.fail(f"{label} is required (non-interactive mode — pass as flag)")
        raise SystemExit(2)

    needs_cred_prompt = interactive and (not args.openai_key or not args.pat)
    if needs_cred_prompt:
        ui.console.print("  [brand]credentials[/brand]")
    openai_key = _need(args.openai_key, "OpenAI API key", password=True)
    pat        = _need(args.pat,        "GitHub PAT (scopes: repo)", password=True)
    if needs_cred_prompt:
        ui.newline()

    needs_source_prompt = interactive and (not args.sdk_repo or not args.mcp_repo)
    if needs_source_prompt:
        ui.console.print("  [brand]sources[/brand]")
    sdk_repo = _need(args.sdk_repo, "SDK source  (local path or owner/repo)")
    mcp_repo = _need(args.mcp_repo, "MCP repo    (owner/repo)")
    if needs_source_prompt:
        ui.newline()

    workspace = project_root / _config.WORKSPACE_DIRNAME
    workspace.mkdir(parents=True, exist_ok=True)

    with ui.step(f"resolving SDK source [accent]{sdk_repo}[/accent]"):
        sdk_path = _config.resolve_sdk_source(sdk_repo, workspace)
    ui.hint(f"resolved → {sdk_path}")

    with ui.step("detecting SDK conventions"):
        glob = _detect_resources_glob(sdk_path)
    if glob:
        ui.hint(f"resources glob → [value]{glob}[/value]")
    else:
        ui.warn("could not auto-detect a resources directory")
        glob = "**/resources/*.py"
    if interactive:
        glob = ui.prompt("resources glob", default=glob)

    base_classes = _detect_base_classes(sdk_path, glob)
    if base_classes:
        ui.hint("base classes → [value]" + ", ".join(base_classes) + "[/value]")
    if interactive:
        answer = ui.prompt(
            "resource base classes (comma-separated, blank for any)",
            default=",".join(base_classes),
        )
        base_classes = [s.strip() for s in answer.split(",") if s.strip()]

    slug_fallback = sdk_repo.rsplit("/", 1)[-1]
    import_module = _detect_import_module(sdk_path, slug_fallback)
    ui.hint(f"import module → [value]{import_module}[/value]")
    if interactive:
        import_module = ui.prompt("python import name", default=import_module)

    default_client = f"{import_module}.Client()"
    client_expression = (
        ui.prompt("client expression in generated tools", default=default_client)
        if interactive else default_client
    )
    exception_class = (
        ui.prompt("exception class to catch", default="Exception")
        if interactive else "Exception"
    )

    ui.newline()
    toml_body = _render_toml(
        sdk_source=sdk_repo,
        resources_glob=glob,
        resource_base_classes=base_classes,
        import_module=import_module,
        client_expression=client_expression,
        exception_class=exception_class,
        mcp_repo=mcp_repo,
        model=args.model,
    )
    toml_path.write_text(toml_body)
    ui.ok(f"wrote [value]{toml_path.name}[/value]")

    if env_path.exists() and not args.force:
        ui.info(f"{env_path.name} already exists — leaving as-is")
    else:
        env_path.write_text(
            "OPENAI_API_KEY=" + openai_key + "\n"
            "PAT_TOKEN=" + pat + "\n"
        )
        try:
            os.chmod(env_path, 0o600)
        except OSError:
            pass
        ui.ok(f"wrote [value]{env_path.name}[/value] (chmod 600)")

    if _write_gitignore(project_root):
        ui.ok("updated [value].gitignore[/value]")

    ui.newline()
    ui.console.print("  next  [kbd]prmcp up[/kbd]    boot the watcher")
    ui.console.print("        [kbd]prmcp run[/kbd]   one-shot pass")
    ui.newline()
    return 0


def _render_toml(
    *,
    sdk_source: str,
    resources_glob: str,
    resource_base_classes: list[str],
    import_module: str,
    client_expression: str,
    exception_class: str,
    mcp_repo: str,
    model: str,
) -> str:
    bases_inline = ", ".join(f'"{b}"' for b in resource_base_classes)
    return (
        "[sdk]\n"
        f'source = "{sdk_source}"\n'
        f'resources_glob = "{resources_glob}"\n'
        f"resource_base_classes = [{bases_inline}]\n"
        f'import_module = "{import_module}"\n'
        f'client_expression = "{client_expression}"\n'
        f'exception_class = "{exception_class}"\n'
        "# client_path = \"path/to/client.py\"  # optional: maps Class → attr\n"
        "\n"
        "[mcp]\n"
        f'target_repo = "{mcp_repo}"\n'
        'base_branch = "main"\n'
        'tool_dir = "tools"\n'
        "\n"
        "[llm]\n"
        f'model = "{model}"\n'
        '# base_url = "https://api.openai.com/v1"\n'
        "\n"
        "[ci]\n"
        '# watched_repo = "owner/repo"     # optional: enable the CI watcher\n'
        'workflow = "prmcp.yml"\n'
        "poll_interval_seconds = 30\n"
        "\n"
        "[daemon]\n"
        "poll_interval_seconds = 2.0\n"
        "debounce_seconds = 3.0\n"
        "\n"
        "[pipeline]\n"
        'trace_path = "/tmp/prmcp-trace.jsonl"\n'
        "dry_run = true\n"
    )


# ----------------------------------------------------------------- up


def up(argv: Iterable[str] | None = None) -> int:
    _ = argv
    try:
        cfg = _config.load()
    except _config.ConfigError as e:
        ui.newline()
        ui.fail(str(e))
        ui.newline()
        return 2

    dry_run_str = "[warn]dry-run[/warn]" if cfg.pipeline.dry_run else "[ok]live[/ok]"
    ui.logo()
    ui.banner(
        "prmcp · up",
        [
            ("config", str(cfg.config_path)),
            ("sdk",    f"{cfg.sdk.source}  [muted]→[/muted] {cfg.sdk.resolved_path}"),
            ("target", f"{cfg.mcp.target_repo}  ({dry_run_str})"),
            ("trace",  str(cfg.pipeline.trace_path)),
        ],
    )

    env = os.environ.copy()
    env.setdefault("PRMCP_TRACE_PATH", str(cfg.pipeline.trace_path))

    procs: list[subprocess.Popen] = []

    ui.ok("daemon       [muted]watching " + str(cfg.sdk.resolved_path) + "[/muted]")
    daemon_proc = subprocess.Popen(
        [sys.executable, "-m", "prmcp.daemon"],
        env=env,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    procs.append(daemon_proc)

    if cfg.ci.watched_repo:
        ui.ok(
            f"ci-watcher   [muted]polling {cfg.ci.watched_repo} · "
            f"{cfg.ci.workflow}[/muted]"
        )
        ci_proc = subprocess.Popen(
            [sys.executable, "-m", "prmcp.ci_watcher"],
            env=env,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        procs.append(ci_proc)

    ui.newline()
    ui.console.print("  press [kbd]Ctrl-C[/kbd] to stop")
    ui.newline()

    def shutdown(*_a):
        ui.newline()
        ui.info("shutting down…")
        for p in procs:
            if p.poll() is None:
                try:
                    p.send_signal(signal.SIGINT)
                except Exception:
                    pass
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    while True:
        for p in procs:
            rc = p.poll()
            if rc is not None:
                ui.fail(f"process exited (rc={rc}) — stopping the rest.")
                shutdown()
        try:
            signal.pause()  # type: ignore[attr-defined]
        except AttributeError:
            import time as _t
            _t.sleep(0.5)


# ----------------------------------------------------------------- aliases


def run(argv: Iterable[str] | None = None) -> int:
    from prmcp import run as runmod
    return runmod.main(argv)


def daemon(argv: Iterable[str] | None = None) -> int:
    from prmcp import daemon as dmod
    return dmod.main(argv)


def ci_watcher(argv: Iterable[str] | None = None) -> int:
    from prmcp import ci_watcher as cmod
    return cmod.main(argv)


def tail(argv: Iterable[str] | None = None) -> int:
    from prmcp import live_tail as lmod
    return lmod.main(argv)


# ----------------------------------------------------------------- umbrella


_SUBCOMMANDS = {
    "init": init,
    "up": up,
    "run": run,
    "daemon": daemon,
    "ci-watcher": ci_watcher,
    "tail": tail,
}


def main(argv: Iterable[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        ui.console.print(
            "\n  [brand]prmcp[/brand]  [muted]watch an SDK, auto-synthesize MCP tools, PR them.[/muted]\n\n"
            "  usage  [kbd]prmcp[/kbd] [accent]<command>[/accent] [args…]\n\n"
            "  [accent]init[/accent]        write prmcp.toml + .env in this directory\n"
            "  [accent]up[/accent]          run daemon (+ ci-watcher) in the foreground\n"
            "  [accent]run[/accent]         single pipeline pass\n"
            "  [accent]daemon[/accent]      SDK file watcher only\n"
            "  [accent]ci-watcher[/accent]  GitHub-Actions → local-trace bridge only\n"
            "  [accent]tail[/accent]        live tail of the trace JSONL\n",
        )
        return 0 if args else 2
    name = args[0]
    rest = args[1:]
    if name not in _SUBCOMMANDS:
        ui.fail(f"unknown subcommand [accent]{name}[/accent]")
        return 2
    return _SUBCOMMANDS[name](rest)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
