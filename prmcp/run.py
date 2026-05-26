"""prmcp.run — orchestrator wiring diff_sdk → synth_tool → shadow_agent → open_pr.

Reads config via `prmcp.config.load()` and produces one trace JSONL line per
(resource, method) pair processed. On first run the SDK-derived contract is
written to `.prmcp/sdk-snapshot.json`; subsequent runs diff the current
contract against the snapshot and process only "new" (resource, method)
pairs.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from typing import Any, Iterable

from prmcp import config as _config
from prmcp import diff_sdk, open_pr, shadow_agent, synth_tool, ui

_logger = logging.getLogger("prmcp.run")


_ANNOTATION_TO_JSON_TYPE = {
    "int": "integer",
    "bool": "boolean",
    "float": "number",
    "dict": "object",
    "list": "array",
    "str": "string",
}


def _params_to_schema(params: list[dict]) -> dict:
    properties: dict[str, dict] = {}
    required: list[str] = []
    for p in params:
        ann = (p.get("annotation") or "").lower()
        t = "string"
        for needle, json_t in _ANNOTATION_TO_JSON_TYPE.items():
            if needle in ann:
                t = json_t
                break
        properties[p["name"]] = {"type": t}
        if p.get("required", True):
            required.append(p["name"])
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _baseline_pairs(baseline: dict) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for r in baseline.get("resources", []):
        for m in r.get("methods", []):
            out.add((r["resource"], m["py_name"]))
    return out


def _new_pairs(current: dict, baseline: dict) -> list[tuple[dict, dict]]:
    seen = _baseline_pairs(baseline)
    out: list[tuple[dict, dict]] = []
    for r in current.get("resources", []):
        for m in r.get("methods", []):
            if (r["resource"], m["py_name"]) not in seen:
                out.append((r, m))
    return out


def _append_trace(trace_path, record: dict) -> None:
    try:
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        with open(trace_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")
    except OSError as e:
        _logger.warning("failed to append trace to %s: %s", trace_path, e)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _process_pair(
    *,
    resource: dict,
    method: dict,
    cfg: _config.Config,
) -> dict:
    """Run render → validate → open_pr for one pair. Returns the trace record.

    Renders the pipeline strip (sdk · diff · synth · check · pr) live, lighting
    up each stage as it completes — the visual mnemonic for PRMCP itself.
    """
    from rich.console import Group
    from rich.live import Live
    from rich.text import Text

    tool_name = synth_tool._default_tool_name(
        resource["resource"], method["py_name"]
    )
    record: dict[str, Any] = {
        "ts": _now_iso(),
        "resource": resource["resource"],
        "py_name": method["py_name"],
        "tool_name": tool_name,
    }

    header = Text()
    header.append("▸ ", style="brand")
    header.append(
        f"{resource['resource']}.{method['py_name']}", style="accent bold"
    )
    header.append("   ")
    header.append(tool_name, style="muted")

    # sdk + diff already happened before we got here.
    done = [0, 1]

    def _frame(active: int, *, status: str = "") -> Group:
        body = Group(
            header,
            Text(),
            Text("    ").append_text(ui.stage_strip(active=active, done=done)),
            Text(),
            Text(f"    {status}", style="muted") if status else Text(""),
        )
        return body

    source: str | None = None
    preview: open_pr.PRPreview | None = None
    pr_url: str | None = None
    skip_reason: str | None = None

    ui.console.print()
    with Live(
        _frame(2, status="rendering…"),
        console=ui.console,
        refresh_per_second=12,
        transient=False,
    ) as live:
        try:
            source = synth_tool.render_tool(resource, method, cfg.sdk)
            done.append(2)
            live.update(_frame(3, status=f"validating with {cfg.llm.model}…"))

            schema = _params_to_schema(method.get("params", []))
            verdict = shadow_agent.validate(
                source,
                tool_name,
                schema,
                model=cfg.llm.model,
                base_url=cfg.llm.base_url,
                sdk_label=cfg.sdk.source,
            )
            record["verdict"] = verdict["verdict"]

            if verdict["verdict"] != "valid":
                live.update(_frame(-1, status=f"shadow → [fail]{verdict['verdict']}[/fail]"))
                record["action"] = "skipped"
                skip_reason = verdict.get("reason", "")
                record["url_or_reason"] = skip_reason
                return record

            done.append(3)
            live.update(_frame(4, status="opening PR…"))

            result = open_pr.open_pr(
                source,
                tool_name,
                target=cfg.mcp.target_repo,
                base=cfg.mcp.base_branch,
                tool_dir=cfg.mcp.tool_dir,
                dry_run=cfg.pipeline.dry_run,
            )
            done.append(4)
            live.update(_frame(-1))

            if isinstance(result, open_pr.PRPreview):
                preview = result
                record["action"] = "dry_run"
                record["url_or_reason"] = str(result)
            else:
                pr_url = result
                record["action"] = "pr_opened"
                record["url_or_reason"] = result

        except Exception as e:  # noqa: BLE001
            record["verdict"] = record.get("verdict", "error")
            record["action"] = "error"
            record["url_or_reason"] = f"{type(e).__name__}: {e}"
            live.update(_frame(-1, status=f"[fail]{type(e).__name__}: {e}[/fail]"))
        finally:
            _append_trace(cfg.pipeline.trace_path, record)

    if preview is not None and source is not None:
        _render_pr_preview(preview, source)
    elif pr_url is not None:
        ui.arrow(f"[brand]{pr_url}[/brand]")
    elif skip_reason is not None:
        ui.console.print(f"    [muted]reason:[/muted] {skip_reason}")

    return record


def _render_pr_preview(preview: open_pr.PRPreview, source: str) -> None:
    table = ui.kv_table([
        ("target", preview.target),
        ("branch", preview.branch),
        ("file",   preview.file_path),
        ("title",  preview.title),
    ])
    ui.console.print()
    ui.console.print(table)
    ui.console.print(ui.code_panel(source, title=preview.file_path))


def _load_or_seed_snapshot(cfg: _config.Config, current: dict) -> tuple[dict, bool]:
    """Return (baseline, was_seeded)."""
    snap = cfg.pipeline.snapshot_path
    if snap.is_file():
        return json.loads(snap.read_text()), False
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    return current, True


def _resource_count(contract: dict) -> tuple[int, int]:
    n_res = len(contract.get("resources", []))
    n_meth = sum(len(r.get("methods", [])) for r in contract.get("resources", []))
    return n_res, n_meth


def run(cfg: _config.Config | None = None, *, quiet: bool = False) -> int:
    cfg = cfg or _config.load()

    if not quiet:
        dry = "[warn]dry-run[/warn]" if cfg.pipeline.dry_run else "[ok]live[/ok]"
        ui.wordmark()
        ui.banner(
            "prmcp · run",
            [
                ("sdk",    cfg.sdk.source),
                ("target", f"{cfg.mcp.target_repo}  ({dry})"),
                ("model",  cfg.llm.model),
            ],
        )

    with ui.step("walking SDK"):
        current = diff_sdk.walk(cfg.sdk)
    n_res, n_meth = _resource_count(current)
    ui.hint(f"{n_res} resources · {n_meth} methods")

    baseline, seeded = _load_or_seed_snapshot(cfg, current)
    if seeded:
        ui.ok(f"seeded baseline snapshot at [value]{cfg.pipeline.snapshot_path}[/value]")
        ui.newline()
        return 0

    pairs = _new_pairs(current, baseline)
    if not pairs:
        ui.ok("no new pairs — snapshot is up to date")
        ui.newline()
        return 0

    ui.ok(f"[brand]{len(pairs)}[/brand] new pair(s) detected")

    results: list[dict] = []
    for resource, method in pairs:
        rec = _process_pair(resource=resource, method=method, cfg=cfg)
        results.append(rec)

    _render_summary(results, cfg)
    return 0


def _render_summary(results: list[dict], cfg: _config.Config) -> None:
    from rich.table import Table

    opened = sum(1 for r in results if r.get("action") == "pr_opened")
    dry    = sum(1 for r in results if r.get("action") == "dry_run")
    skipped = sum(1 for r in results if r.get("action") == "skipped")
    errored = sum(1 for r in results if r.get("action") == "error")

    t = Table(
        show_header=True,
        header_style="muted",
        border_style="muted",
        expand=False,
        title=None,
    )
    t.add_column("pair", style="value")
    t.add_column("verdict", style="value")
    t.add_column("action", style="value")
    t.add_column("detail", style="muted", overflow="fold", no_wrap=False)
    for r in results:
        v = r.get("verdict", "")
        v_style = {"valid": "[ok]valid[/ok]", "invalid": "[fail]invalid[/fail]",
                   "error": "[fail]error[/fail]"}.get(v, v)
        a = r.get("action", "")
        a_style = {
            "pr_opened": "[ok]pr_opened[/ok]",
            "dry_run":   "[brand]dry_run[/brand]",
            "skipped":   "[warn]skipped[/warn]",
            "error":     "[fail]error[/fail]",
        }.get(a, a)
        detail = r.get("url_or_reason", "")
        if isinstance(detail, str) and len(detail) > 60:
            detail = detail.splitlines()[0][:60] + "…"
        t.add_row(
            f"{r.get('resource')}.{r.get('py_name')}",
            v_style,
            a_style,
            str(detail),
        )

    ui.newline()
    ui.console.print(t)
    ui.newline()
    summary = (
        f"  [ok]{opened} opened[/ok] · "
        f"[brand]{dry} dry-run[/brand] · "
        f"[warn]{skipped} skipped[/warn] · "
        f"[fail]{errored} errored[/fail]   "
        f"[muted]· trace → {cfg.pipeline.trace_path}[/muted]"
    )
    ui.console.print(summary)
    ui.newline()


def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="prmcp run")
    parser.add_argument(
        "--reseed",
        action="store_true",
        help="overwrite the saved snapshot with the current SDK contract",
    )
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> int:
    logging.basicConfig(
        level=os.environ.get("PRMCP_LOG_LEVEL", "WARNING"),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        cfg = _config.load()
    except _config.ConfigError as e:
        ui.newline()
        ui.fail(str(e))
        ui.newline()
        return 2

    if args.reseed:
        current = diff_sdk.walk(cfg.sdk)
        cfg.pipeline.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        cfg.pipeline.snapshot_path.write_text(
            json.dumps(current, indent=2, sort_keys=True) + "\n"
        )
        n_res, n_meth = _resource_count(current)
        ui.wordmark()
        ui.banner(
            "prmcp · reseed",
            [
                ("sdk",       cfg.sdk.source),
                ("snapshot",  str(cfg.pipeline.snapshot_path)),
                ("resources", f"{n_res}"),
                ("methods",   f"{n_meth}"),
            ],
        )
        ui.ok("baseline frozen — subsequent `prmcp run` only sees what changes from here")
        ui.newline()
        return 0

    return run(cfg)


if __name__ == "__main__":
    raise SystemExit(main())
