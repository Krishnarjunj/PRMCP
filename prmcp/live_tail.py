"""prmcp.live_tail — terminal real-time view of the pipeline.

Reads `$PRMCP_TRACE_PATH` (default `/tmp/prmcp-trace.jsonl`) and renders
each new trace line as it appears, with ANSI colors. Groups consecutive
records into runs (records within 30s of each other are the same run)
and prints a per-run summary footer.

Env vars:

- `PRMCP_TRACE_PATH`      — JSONL trace path (matches prmcp.daemon).
- `PRMCP_TAIL_POLL`       — seconds between polls (default 0.5).
- `PRMCP_TAIL_RUN_GAP`    — seconds of idleness that separates runs (default 30).
- `PRMCP_TAIL_NO_COLOR`   — truthy → strip ANSI codes.
"""
from __future__ import annotations

import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Iterable

# ---- ANSI -----------------------------------------------------------------

_NO_COLOR = os.environ.get("PRMCP_TAIL_NO_COLOR", "").strip().lower() in {
    "1", "true", "yes", "on",
}


def _c(code: str) -> str:
    return "" if _NO_COLOR else code


RESET = _c("\033[0m")
BOLD = _c("\033[1m")
DIM = _c("\033[2m")
GREEN = _c("\033[32m")
RED = _c("\033[31m")
YELLOW = _c("\033[33m")
BLUE = _c("\033[36m")
GREY = _c("\033[90m")

CHECK = f"{GREEN}✓{RESET}"
CROSS = f"{RED}✗{RESET}"
WARN = f"{YELLOW}⚠{RESET}"
DASH = f"{GREY}—{RESET}"

# ---- Helpers --------------------------------------------------------------


def _trace_path() -> Path:
    return Path(os.environ.get("PRMCP_TRACE_PATH", "/tmp/prmcp-trace.jsonl"))


def _ts_epoch(ts: str) -> float:
    return time.mktime(time.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S"))


def _hms(ts: str) -> str:
    return ts[11:19]


def _truncate(s: str, n: int) -> str:
    s = s.replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


# ---- Rendering ------------------------------------------------------------


def _stage_line(verdict: str, action: str) -> str:
    """Render the per-pair stage badges in one line."""
    if verdict == "valid":
        shadow = f"shadow {CHECK} {GREEN}VALID{RESET}"
    elif verdict == "invalid":
        shadow = f"shadow {CROSS} {RED}INVALID{RESET}"
    else:
        shadow = f"shadow {CROSS} {RED}ERROR{RESET}"

    if action == "pr_opened":
        open_pr = f"open_pr {CHECK}"
    elif action == "dry_run":
        open_pr = f"open_pr {CHECK} {DIM}(dry){RESET}"
    elif action == "skipped":
        open_pr = f"open_pr {DASH}"
    elif action == "error":
        open_pr = f"open_pr {CROSS}"
    else:
        open_pr = f"open_pr {DASH}"

    return f"  trigger {CHECK}  diff {CHECK}  synth {CHECK}  {shadow}  {open_pr}"


def _render_pair(rec: dict) -> None:
    verdict = rec.get("verdict", "")
    action = rec.get("action", "")
    resource = rec.get("resource", "?")
    py_name = rec.get("py_name", "?")
    info = rec.get("url_or_reason", "")

    if action in ("pr_opened", "dry_run"):
        head = CHECK
        title_color = GREEN
    elif verdict == "invalid":
        head = CROSS
        title_color = RED
    elif action == "error":
        head = WARN
        title_color = YELLOW
    else:
        head = DASH
        title_color = ""

    title = f"{title_color}{resource}.{py_name}{RESET}"
    print(f"{head} {BOLD}{title}{RESET}")
    print(_stage_line(verdict, action))

    if action == "pr_opened":
        print(f"    {BLUE}→ {info}{RESET}")
    elif action == "dry_run":
        print(f"    {DIM}→ dry-run preview (no real PR){RESET}")
    elif verdict == "invalid":
        print(f"    {RED}rejected:{RESET} {_truncate(info, 90)}")
    elif action == "error":
        first = info.split(":", 1)[0] if ":" in info else info
        print(f"    {RED}error:{RESET} {_truncate(first, 90)}")
    print()


def _hr(width: int = 72, color: str = GREY) -> str:
    return f"{color}{'─' * width}{RESET}"


def _print_run_header(first_rec: dict) -> None:
    ts = _hms(first_rec["ts"])
    print(f"{BOLD}{BLUE}[{ts}]{RESET}  {BOLD}run start{RESET}")
    print(_hr())


def _print_run_footer(run: list[dict]) -> None:
    opened = sum(1 for l in run if l.get("action") in ("pr_opened", "dry_run"))
    rejected = sum(1 for l in run if l.get("verdict") == "invalid")
    errored = sum(1 for l in run if l.get("action") == "error")
    total = len(run)

    if opened == total:
        col = GREEN
        verdict = "all opened"
    elif opened == 0:
        col = RED
        verdict = "no PRs opened"
    else:
        col = YELLOW
        verdict = "partial"

    stats = (
        f"{col}{opened}/{total} opened{RESET}  ·  "
        f"{RED if rejected else DIM}{rejected} rejected{RESET}  ·  "
        f"{YELLOW if errored else DIM}{errored} errored{RESET}  ·  "
        f"{col}{verdict}{RESET}"
    )
    print(_hr())
    print(f"  {stats}")
    print()
    print()


# ---- Main loop ------------------------------------------------------------


def _read_all_lines(path: Path) -> list[dict]:
    out: list[dict] = []
    try:
        with path.open() as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    out.append(json.loads(raw))
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        return []
    return out


def watch(
    *,
    trace_path: Path | None = None,
    poll: float | None = None,
    run_gap: float | None = None,
) -> int:
    trace_path = trace_path or _trace_path()
    poll = float(poll if poll is not None else os.environ.get("PRMCP_TAIL_POLL", "0.5"))
    run_gap = float(
        run_gap if run_gap is not None else os.environ.get("PRMCP_TAIL_RUN_GAP", "30")
    )

    print()
    print(f"{BOLD}PRMCP pipeline · live tail{RESET}")
    print(f"{DIM}{trace_path}{RESET}")
    print(_hr(72, GREY))
    print()

    if not trace_path.exists():
        try:
            trace_path.touch()
        except OSError:
            pass

    stop = {"flag": False}

    def _on_signal(signum, _frame):  # noqa: ANN001
        stop["flag"] = True

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    rendered = 0
    open_run: list[dict] = []
    last_ts = 0.0

    while not stop["flag"]:
        all_lines = _read_all_lines(trace_path)

        # Stream any new lines through the renderer.
        for rec in all_lines[rendered:]:
            ts = _ts_epoch(rec["ts"])
            if open_run and ts - last_ts > run_gap:
                _print_run_footer(open_run)
                open_run = []

            if not open_run:
                _print_run_header(rec)

            _render_pair(rec)
            sys.stdout.flush()
            open_run.append(rec)
            last_ts = ts

        rendered = len(all_lines)

        # If the open run has been idle longer than run_gap, close it.
        if open_run and time.time() - last_ts > run_gap:
            _print_run_footer(open_run)
            open_run = []

        time.sleep(poll)

    # Flush a final footer on Ctrl-C so the user sees the running totals.
    if open_run:
        _print_run_footer(open_run)
    print(f"{DIM}— stopped —{RESET}")
    return 0


def main(argv: Iterable[str] | None = None) -> int:
    _ = argv
    return watch()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
