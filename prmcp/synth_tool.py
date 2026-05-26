"""prmcp.synth_tool — Render @mcp.tool() functions from diff_sdk contracts.

Consumes the JSON contract produced by `diff_sdk.walk()`. Emits Python
source for a complete @mcp.tool() function per (resource, method) pair,
using Jinja2 templates routed by `verb`.

Contract (version 1):

    {
      "contract_version": 1,
      "resources": [
        {
          "resource": "<file-stem or file-stem.ClassName>",
          "class_name": "<python class name>",
          "shape": "standard" | "sub_resource",
          "source_path": "<path relative to sdk root>",
          "client_attr": "<attribute on the client expression>",
          "methods": [
            {
              "verb": "create" | "get" | "update" | "delete" | "list" | "other",
              "py_name": "<sdk method name>",
              "params": [
                {"name": "...", "annotation": "...", "default": ..., "required": ...},
                ...
              ],
              "docstring": "<verbatim from SDK>",
              "returns": "<annotation or null>"
            }
          ]
        }
      ]
    }

Both producer (diff_sdk) and consumer (synth_tool) MUST check
`contract_version == 1`; raise on mismatch.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from prmcp import config as _config

CONTRACT_VERSION = 1

TEMPLATES_DIR = Path(__file__).parent / "templates"

VERB_TO_TEMPLATE = {
    "get": "tool_get.py.j2",
    "create": "tool_create.py.j2",
    "update": "tool_update.py.j2",
    "delete": "tool_delete.py.j2",
    "list": "tool_list.py.j2",
    "other": "tool_passthrough.py.j2",
}


class ContractVersionError(ValueError):
    pass


def check_contract_version(contract: dict) -> None:
    v = contract.get("contract_version")
    if v != CONTRACT_VERSION:
        raise ContractVersionError(
            f"contract_version mismatch: got {v!r}, expected {CONTRACT_VERSION}. "
            "Bump in lockstep with diff_sdk.py."
        )


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        keep_trailing_newline=True,
        trim_blocks=False,
        lstrip_blocks=False,
        autoescape=False,
    )


def _render_default(value: Any) -> str:
    if value is None:
        return "None"
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        # diff_sdk emits ast.unparse() output, which is already Python source.
        return value
    return repr(value)


def _render_param(p: dict) -> str:
    name = p["name"]
    ann = p.get("annotation") or "Any"
    if p.get("required", True):
        return f"{name}: {ann}"
    return f"{name}: {ann} = {_render_default(p.get('default'))}"


def render_signature(params: list[dict]) -> str:
    return ", ".join(_render_param(p) for p in params)


def render_kwargs(params: list[dict]) -> str:
    return ", ".join(f"{p['name']}={p['name']}" for p in params)


def render_docstring_block(docstring: str, indent: int = 4) -> str:
    pad = " " * indent
    if not docstring:
        return '""""""'
    if "\n" not in docstring:
        return f'"""{docstring}"""'
    lines = docstring.split("\n")
    head = lines[0]
    tail = "\n".join((pad + line) if line.strip() else "" for line in lines[1:])
    return f'"""{head}\n{tail}\n{pad}"""'


_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def _snake_case_segment(seg: str) -> str:
    return _CAMEL_BOUNDARY.sub("_", seg).lower()


def _default_tool_name(resource_name: str, py_name: str) -> str:
    parts = [_snake_case_segment(seg) for seg in resource_name.split(".")]
    return "_".join(parts + [py_name])


def _default_client_expression(sdk: _config.SdkConfig) -> str:
    if sdk.client_expression:
        return sdk.client_expression
    return f"{sdk.import_module}.Client()"


def render_tool(
    resource: dict,
    method_spec: dict,
    sdk: _config.SdkConfig,
    *,
    tool_name: str | None = None,
) -> str:
    """Render a single @mcp.tool() function as Python source."""
    verb = method_spec.get("verb", "other")
    template_name = VERB_TO_TEMPLATE.get(verb, VERB_TO_TEMPLATE["other"])
    params = method_spec.get("params", [])
    client_attr = resource.get("client_attr") or resource["resource"]
    ctx = {
        "tool_name": tool_name
        or _default_tool_name(resource["resource"], method_spec["py_name"]),
        "params": params,
        "signature": render_signature(params),
        "kwargs": render_kwargs(params),
        "docstring": method_spec.get("docstring", "") or "",
        "docstring_block": render_docstring_block(
            method_spec.get("docstring", "") or ""
        ),
        "resource": resource["resource"],
        "client_attr": client_attr,
        "sdk_method": method_spec["py_name"],
        "returns": method_spec.get("returns", "dict"),
        "client_expression": _default_client_expression(sdk),
        "exception_class": sdk.exception_class,
    }
    return _env().get_template(template_name).render(**ctx)


def render_contract(contract: dict, sdk: _config.SdkConfig) -> list[str]:
    check_contract_version(contract)
    out: list[str] = []
    for r in contract.get("resources", []):
        for m in r.get("methods", []):
            out.append(render_tool(r, m, sdk))
    return out


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in {"-h", "--help"}:
        print("usage: synth_tool  (reads contract JSON from stdin)", file=sys.stderr)
        return 2
    cfg = _config.load()
    contract = json.load(sys.stdin)
    sources = render_contract(contract, cfg.sdk)
    sys.stdout.write("\n\n".join(sources))
    if sources:
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
