"""prmcp.ui — Rich-based TUI helpers shared across CLI subcommands.

One console instance, one theme, a few small helpers so every subcommand
looks like part of the same product.
"""
from __future__ import annotations

import sys
from contextlib import contextmanager
from typing import Iterator

from rich.align import Align
from rich.console import Console, Group
from rich.panel import Panel
from rich.prompt import Prompt
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

from prmcp import __version__ as _VERSION

THEME = Theme(
    {
        "brand": "bold #7aa2f7",
        "brand.dim": "#7aa2f7",
        "accent": "bold #bb9af7",
        "ok": "bold #9ece6a",
        "warn": "bold #e0af68",
        "fail": "bold #f7768e",
        "muted": "#565f89",
        "label": "#7dcfff",
        "value": "default",
        "kbd": "italic #c0caf5",
    }
)

console = Console(theme=THEME, highlight=False)


GLYPH_OK = "[ok]✓[/ok]"
GLYPH_FAIL = "[fail]✗[/fail]"
GLYPH_WARN = "[warn]![/warn]"
GLYPH_DOT = "[muted]·[/muted]"
GLYPH_ARROW = "[brand]→[/brand]"


# ──────────────────────────────────────────── logo ─────────────────────────
#
# ANSI-Shadow figlet for "PRMCP". We hand-split the columns so the first
# 16 chars (the "PR " portion) render in `brand` and the rest (the "MCP"
# portion) render in `accent`. This visually reinforces the mnemonic:
# `prmcp` = `pr` × `mcp` = pull request × model context protocol.

LOGO_LINES: tuple[str, ...] = (
    "██████╗ ██████╗ ███╗   ███╗ ██████╗██████╗ ",
    "██╔══██╗██╔══██╗████╗ ████║██╔════╝██╔══██╗",
    "██████╔╝██████╔╝██╔████╔██║██║     ██████╔╝",
    "██╔═══╝ ██╔══██╗██║╚██╔╝██║██║     ██╔═══╝ ",
    "██║     ██║  ██║██║ ╚═╝ ██║╚██████╗██║     ",
    "╚═╝     ╚═╝  ╚═╝╚═╝     ╚═╝ ╚═════╝╚═╝     ",
)

# Column where the "MCP" half begins (right after `PR `).
_PR_MCP_SPLIT = 16

# Pipeline stages the tool walks for each new (resource, method) pair.
# These mirror the architecture diagram and the run loop's actual order.
PIPELINE_STAGES: tuple[str, ...] = ("sdk", "diff", "synth", "check", "pr")


def _logo_block(centered: bool = False) -> Group:
    body = Text()
    for i, line in enumerate(LOGO_LINES):
        if i:
            body.append("\n")
        body.append(line[:_PR_MCP_SPLIT], style="brand")
        body.append(line[_PR_MCP_SPLIT:], style="accent")

    tagline = Text()
    tagline.append("pull request", style="brand")
    tagline.append("  ", style="muted")
    tagline.append("×", style="muted")
    tagline.append("  ", style="muted")
    tagline.append("model context protocol", style="accent")

    pipe = Text()
    for i, stage in enumerate(PIPELINE_STAGES):
        if i:
            pipe.append("  ", style="muted")
            pipe.append("►", style="brand.dim")
            pipe.append("  ", style="muted")
        pipe.append(stage, style="muted")

    version = Text(f"v{_VERSION}", style="muted")

    inner = Group(body, Text(), tagline, pipe, Text(), version)
    if centered:
        return Group(Align.center(inner))
    return inner


def logo() -> None:
    """Print the full PRMCP banner — used by `prmcp init` and `prmcp up`."""
    console.print()
    console.print(_logo_block())
    console.print()


def wordmark() -> None:
    """One-line PRMCP wordmark — used by `prmcp run` (less vertical real estate)."""
    line = Text()
    line.append("▌▌ ", style="brand")
    line.append("prmcp", style="brand bold")
    line.append("  ", style="muted")
    line.append("pull request", style="brand")
    line.append(" × ", style="muted")
    line.append("model context protocol", style="accent")
    line.append(f"   v{_VERSION}", style="muted")
    console.print()
    console.print(line)


def stage_strip(active: int = -1, done: list[int] | None = None) -> Text:
    """Render the pipeline as 'sdk ─► diff ─► synth ─► check ─► pr', highlighting
    the currently-active stage and dimming the ones that already ran."""
    done = done or []
    t = Text()
    for i, stage in enumerate(PIPELINE_STAGES):
        if i:
            t.append("  ►  ", style="muted")
        if i == active:
            t.append(stage, style="brand bold")
        elif i in done:
            t.append(stage, style="ok")
        else:
            t.append(stage, style="muted")
    return t


def banner(title: str, lines: list[tuple[str, str]]) -> None:
    """Show a header panel with a title and a few label/value pairs.

    `lines` is `[(label, value), ...]`. `value` may include Rich markup
    (e.g. `[warn]dry-run[/warn]`).
    """
    body = Text()
    pad = max(len(label) for label, _ in lines) if lines else 0
    for i, (label, value) in enumerate(lines):
        if i:
            body.append("\n")
        body.append(label.ljust(pad), style="label")
        body.append("  ")
        body.append(Text.from_markup(value))
    console.print()
    console.print(
        Panel(
            body,
            title=Text(title, style="brand"),
            title_align="left",
            border_style="muted",
            padding=(0, 1),
        )
    )
    console.print()


@contextmanager
def step(message: str) -> Iterator[None]:
    """Spinner while a block runs, replaced with a check or cross on exit."""
    with console.status(f"[muted]{message}…[/muted]", spinner="dots") as s:
        try:
            yield
        except Exception:
            s.stop()
            console.print(f"  {GLYPH_FAIL} {message}")
            raise
        else:
            s.stop()
            console.print(f"  {GLYPH_OK} {message}")


def ok(message: str) -> None:
    console.print(f"  {GLYPH_OK} {message}")


def info(message: str) -> None:
    console.print(f"  {GLYPH_DOT} [muted]{message}[/muted]")


def warn(message: str) -> None:
    console.print(f"  {GLYPH_WARN} [warn]{message}[/warn]")


def fail(message: str) -> None:
    console.print(f"  {GLYPH_FAIL} [fail]{message}[/fail]")


def arrow(message: str) -> None:
    console.print(f"  {GLYPH_ARROW} {message}")


def kv_table(rows: list[tuple[str, str]]) -> Table:
    t = Table.grid(padding=(0, 2))
    t.add_column(style="label")
    t.add_column(style="value")
    for k, v in rows:
        t.add_row(k, v)
    return t


def code_panel(source: str, *, title: str | None = None) -> Panel:
    syn = Syntax(
        source.rstrip(),
        "python",
        theme="monokai",
        line_numbers=False,
        word_wrap=False,
        background_color="default",
    )
    return Panel(
        syn,
        title=Text(title, style="brand") if title else None,
        title_align="left",
        border_style="muted",
        padding=(0, 1),
    )


def prompt(
    label: str,
    *,
    default: str | None = None,
    password: bool = False,
    choices: list[str] | None = None,
) -> str:
    """Rich prompt with a consistent look."""
    return Prompt.ask(
        f"[label]{label}[/label]",
        default=default,
        password=password,
        choices=choices,
        show_default=default is not None and not password,
        console=console,
    )


def hint(message: str) -> None:
    console.print(f"  [muted]{message}[/muted]")


def newline() -> None:
    console.print()


def is_tty() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()
