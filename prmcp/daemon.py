"""prmcp.daemon — watch the configured SDK source for changes and auto-run
the pipeline.

Polls every file matched by `[sdk] resources_glob` (relative to the resolved
SDK path) for mtime changes, debounces a configurable window, and then calls
`prmcp.run.run` to process any new (resource, method) pairs. Every pair
processed appends a JSONL line to `[pipeline] trace_path`.

Designed so:

- **No extra runtime deps.** `os.stat` polling beats inotify/watchdog for
  cross-platform reliability.
- **Debounced.** Bursts of edits coalesce into one pipeline run.
- **Resilient.** A failed run logs the traceback and keeps watching.
"""
from __future__ import annotations

import logging
import os
import signal
import sys
import time
import traceback
from pathlib import Path
from typing import Iterable

from prmcp import config as _config
from prmcp import run as runmod

_logger = logging.getLogger("prmcp.daemon")


def _resource_files(cfg: _config.Config) -> list[Path]:
    root = cfg.sdk.resolved_path
    return sorted(
        p for p in root.glob(cfg.sdk.resources_glob)
        if p.is_file() and p.suffix == ".py" and p.stem != "__init__"
    )


def _snapshot_mtimes(files: list[Path]) -> dict[str, float]:
    out: dict[str, float] = {}
    for p in files:
        try:
            out[str(p)] = p.stat().st_mtime
        except OSError:
            continue
    return out


def _diff_mtimes(prev: dict[str, float], curr: dict[str, float]) -> list[str]:
    changed: list[str] = []
    for name, mtime in curr.items():
        if prev.get(name) != mtime:
            changed.append(name)
    for name in prev:
        if name not in curr:
            changed.append(name)
    return sorted(set(changed))


def _trigger(cfg: _config.Config) -> None:
    _logger.info(
        "trigger: sdk=%s target=%s dry_run=%s",
        cfg.sdk.source, cfg.mcp.target_repo, cfg.pipeline.dry_run,
    )
    try:
        runmod.run(cfg)
    except Exception:
        _logger.error("pipeline run failed:\n%s", traceback.format_exc())


def watch(cfg: _config.Config | None = None) -> int:
    cfg = cfg or _config.load()
    files = _resource_files(cfg)

    if not files:
        _logger.error(
            "no SDK resource files matched glob %r under %s — "
            "check [sdk] resources_glob in prmcp.toml.",
            cfg.sdk.resources_glob, cfg.sdk.resolved_path,
        )
        return 2

    _logger.info(
        "watching %d file(s) under %s (poll=%.1fs debounce=%.1fs target=%s dry_run=%s)",
        len(files), cfg.sdk.resolved_path,
        cfg.daemon.poll_interval_seconds, cfg.daemon.debounce_seconds,
        cfg.mcp.target_repo, cfg.pipeline.dry_run,
    )

    stop = {"flag": False}

    def _on_signal(signum, _frame):  # noqa: ANN001
        _logger.info("received signal %s — shutting down", signum)
        stop["flag"] = True

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    prev = _snapshot_mtimes(files)
    last_change_at: float | None = None
    last_trigger_at: float = 0.0

    _trigger(cfg)
    last_trigger_at = time.time()

    while not stop["flag"]:
        time.sleep(cfg.daemon.poll_interval_seconds)
        files = _resource_files(cfg)
        curr = _snapshot_mtimes(files)
        changed = _diff_mtimes(prev, curr)
        if changed:
            prev = curr
            last_change_at = time.time()
            _logger.info(
                "detected change in %d file(s): %s",
                len(changed),
                ", ".join(Path(c).name for c in changed[:4])
                + ("…" if len(changed) > 4 else ""),
            )
            continue

        if last_change_at is None:
            continue
        if time.time() - last_change_at < cfg.daemon.debounce_seconds:
            continue
        if last_trigger_at >= last_change_at:
            last_change_at = None
            continue

        _trigger(cfg)
        last_trigger_at = time.time()
        last_change_at = None

    return 0


def main(argv: Iterable[str] | None = None) -> int:
    logging.basicConfig(
        level=os.environ.get("PRMCP_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    _ = argv
    return watch()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
