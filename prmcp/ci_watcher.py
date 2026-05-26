"""prmcp.ci_watcher — bridge GitHub Actions runs into the local trace.

When `[ci] watched_repo` is set in `prmcp.toml`, this watcher polls
`gh run list` for newly-completed runs of the configured workflow,
downloads each new run's `*.jsonl` artifact, and appends the lines to
the local trace file. The terminal `prmcp-tail` and any external
viewers pick up the new records.

Designed alongside `prmcp.daemon`:

- **No extra runtime deps.** Shells out to the `gh` CLI.
- **Idempotent.** Tracks the highest run ID seen in
  `.prmcp/ci-watcher.state`. Restarts don't replay.
- **First-boot quiet.** Seeds state with the current latest run so the
  watcher doesn't backfill history; only genuinely new runs after boot
  are streamed.
- **Resilient.** A poll failure logs the traceback and the loop continues.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path
from typing import Iterable

from prmcp import config as _config

_logger = logging.getLogger("prmcp.ci_watcher")


def _state_path(workspace: Path) -> Path:
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace / _config.CI_STATE_FILENAME


def _load_last_seen(state: Path) -> int:
    if not state.is_file():
        return 0
    try:
        return int(state.read_text().strip() or "0")
    except (ValueError, OSError):
        return 0


def _save_last_seen(state: Path, run_id: int) -> None:
    try:
        state.write_text(str(run_id))
    except OSError as e:
        _logger.warning("could not persist state: %s", e)


def _gh_list_completed(repo: str, workflow: str, limit: int = 10) -> list[int]:
    try:
        out = subprocess.check_output(
            [
                "gh", "run", "list",
                "-R", repo,
                "--workflow", workflow,
                "--status", "completed",
                "-L", str(limit),
                "--json", "databaseId",
            ],
            text=True,
        )
    except subprocess.CalledProcessError as e:
        _logger.error("gh run list failed (rc=%s)", e.returncode)
        return []
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        _logger.error("gh run list returned non-JSON: %r", out[:200])
        return []
    return [int(item["databaseId"]) for item in data if "databaseId" in item]


def _gh_download_trace_lines(repo: str, run_id: int) -> list[str]:
    with tempfile.TemporaryDirectory(prefix=f"prmcp-ci-{run_id}-") as tmp:
        try:
            subprocess.check_call(
                ["gh", "run", "download", str(run_id), "-R", repo, "-D", tmp],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError as e:
            _logger.warning("no artifact for run %s (rc=%s)", run_id, e.returncode)
            return []
        lines: list[str] = []
        for path in Path(tmp).rglob("*.jsonl"):
            try:
                for raw in path.read_text().splitlines():
                    if raw.strip():
                        lines.append(raw if raw.endswith("\n") else raw + "\n")
            except OSError:
                continue
        return lines


def _append(trace_path: Path, lines: Iterable[str]) -> int:
    n = 0
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    with trace_path.open("a") as f:
        for line in lines:
            f.write(line)
            n += 1
    return n


def watch(cfg: _config.Config | None = None) -> int:
    cfg = cfg or _config.load()

    if not cfg.ci.watched_repo:
        _logger.info(
            "no [ci] watched_repo configured — ci_watcher has nothing to do."
        )
        return 0

    if shutil.which("gh") is None:
        _logger.error("gh CLI not on PATH — install gh (https://cli.github.com).")
        return 2

    repo = cfg.ci.watched_repo
    workflow = cfg.ci.workflow
    trace_path = cfg.pipeline.trace_path
    poll = cfg.ci.poll_interval_seconds

    state = _state_path(cfg.workspace)
    last_seen = _load_last_seen(state)

    if last_seen == 0:
        ids = _gh_list_completed(repo, workflow, limit=1)
        if ids:
            last_seen = ids[0]
            _save_last_seen(state, last_seen)
            _logger.info("first boot — seeded last_seen=%d (no backfill)", last_seen)
        else:
            _logger.info(
                "first boot — no prior runs found; will pick up the next one"
            )

    _logger.info(
        "watching %s workflow=%s trace=%s poll=%.0fs last_seen=%d",
        repo, workflow, trace_path, poll, last_seen,
    )

    stop = {"flag": False}

    def _on_signal(signum, _frame):  # noqa: ANN001
        _logger.info("received signal %s — shutting down", signum)
        stop["flag"] = True

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    while not stop["flag"]:
        try:
            ids = _gh_list_completed(repo, workflow, limit=10)
            new_ids = sorted(i for i in ids if i > last_seen)
            for run_id in new_ids:
                if stop["flag"]:
                    break
                _logger.info("new completed run: %d — fetching artifact", run_id)
                lines = _gh_download_trace_lines(repo, run_id)
                if lines:
                    n = _append(trace_path, lines)
                    _logger.info("appended %d trace line(s) from run %d", n, run_id)
                else:
                    _logger.info("run %d had no trace artifact — marking seen", run_id)
                last_seen = run_id
                _save_last_seen(state, last_seen)
        except Exception:
            _logger.error("poll cycle failed:\n%s", traceback.format_exc())

        slept = 0.0
        while slept < poll and not stop["flag"]:
            time.sleep(min(1.0, poll - slept))
            slept += 1.0

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
