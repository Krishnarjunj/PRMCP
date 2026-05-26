"""AST-walk the user's SDK source and emit the normalized PRMCP JSON contract.

Producer side of the diff_sdk → synth_tool contract. contract_version: 1.
Both sides MUST check the version field and raise on mismatch — bump in
lockstep when the schema changes.

Configuration is supplied by `prmcp.config.SdkConfig`:

- `resolved_path`           — root of the SDK checkout to walk.
- `resources_glob`          — glob (relative to `resolved_path`) for resource
                              files, e.g. `"src/myapi/resources/*.py"`.
- `resource_base_classes`   — class names treated as resource markers
                              (e.g. `["BaseResource", "ResourceInterface"]`).
                              An empty list means "treat every public class
                              with public methods as a resource".
- `client_path`             — optional. If set, the file's `Client.__init__`
                              (or any single top-level class with an
                              `__init__`) is parsed to build the
                              {class_name: attr_name} map.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Optional

from prmcp import config as _config

CONTRACT_VERSION = 1

_VERB_KEYWORDS = frozenset({"get", "create", "update", "delete", "list"})


def _base_names(cls: ast.ClassDef) -> list[str]:
    names: list[str] = []
    for b in cls.bases:
        if isinstance(b, ast.Name):
            names.append(b.id)
        elif isinstance(b, ast.Attribute):
            names.append(b.attr)
    return names


def _matches_base(cls: ast.ClassDef, accepted: tuple[str, ...]) -> bool:
    if not accepted:
        return True
    bases = _base_names(cls)
    return any(b in accepted for b in bases)


def _public_classes(tree: ast.Module, accepted: tuple[str, ...]) -> list[ast.ClassDef]:
    return [
        n for n in tree.body
        if isinstance(n, ast.ClassDef)
        and not n.name.startswith("_")
        and _matches_base(n, accepted)
    ]


def _verb(method_name: str) -> str:
    return method_name if method_name in _VERB_KEYWORDS else "other"


def _unparse_or_none(node: Optional[ast.AST]) -> Optional[str]:
    if node is None:
        return None
    return ast.unparse(node)


def _extract_params(fn: ast.FunctionDef) -> list[dict]:
    args = fn.args.args
    defaults = fn.args.defaults
    n_args = len(args)
    n_defaults = len(defaults)
    out: list[dict] = []
    for i, a in enumerate(args):
        if a.arg in ("self", "cls"):
            continue
        default_idx = i - (n_args - n_defaults)
        if default_idx >= 0:
            default = _unparse_or_none(defaults[default_idx])
            required = False
        else:
            default = None
            required = True
        out.append({
            "name": a.arg,
            "annotation": _unparse_or_none(a.annotation),
            "default": default,
            "required": required,
        })
    for j, a in enumerate(fn.args.kwonlyargs):
        kw_default = fn.args.kw_defaults[j]
        if kw_default is None:
            default = None
            required = True
        else:
            default = _unparse_or_none(kw_default)
            required = False
        out.append({
            "name": a.arg,
            "annotation": _unparse_or_none(a.annotation),
            "default": default,
            "required": required,
        })
    return out


def _extract_methods(cls: ast.ClassDef) -> list[dict]:
    methods: list[dict] = []
    for node in cls.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name.startswith("_"):
            continue
        methods.append({
            "verb": _verb(node.name),
            "py_name": node.name,
            "params": _extract_params(node),
            "docstring": ast.get_docstring(node),
            "returns": _unparse_or_none(node.returns),
        })
    return methods


def _detect(
    file_stem: str, rel_source: str, tree: ast.Module, accepted: tuple[str, ...]
) -> list[dict]:
    classes = _public_classes(tree, accepted)
    classes = [c for c in classes if any(
        isinstance(b, ast.FunctionDef) and not b.name.startswith("_") for b in c.body
    )]
    if not classes:
        return []
    if len(classes) == 1:
        cls = classes[0]
        return [{
            "resource": file_stem,
            "class_name": cls.name,
            "shape": "standard",
            "source_path": rel_source,
            "methods": _extract_methods(cls),
        }]
    return [
        {
            "resource": f"{file_stem}.{cls.name}",
            "class_name": cls.name,
            "shape": "sub_resource",
            "source_path": rel_source,
            "methods": _extract_methods(cls),
        }
        for cls in classes
    ]


def build_client_attr_map(sdk_root: Path, client_path: str | None) -> dict[str, str]:
    """Parse the user's client file's `__init__` and return
    `{ClassName: client_attr_name}`. Returns {} if no client_path was
    configured."""
    if not client_path:
        return {}
    cp = sdk_root / client_path
    if not cp.exists():
        raise FileNotFoundError(f"[sdk] client_path does not exist: {cp}")
    tree = ast.parse(cp.read_text())
    client_cls: ast.ClassDef | None = next(
        (n for n in tree.body if isinstance(n, ast.ClassDef)),
        None,
    )
    if client_cls is None:
        return {}
    init = next(
        (n for n in client_cls.body
         if isinstance(n, ast.FunctionDef) and n.name == "__init__"),
        None,
    )
    if init is None:
        return {}
    mapping: dict[str, str] = {}
    for stmt in init.body:
        if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
            continue
        target = stmt.targets[0]
        if not (isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"):
            continue
        value = stmt.value
        if not (isinstance(value, ast.Call) and isinstance(value.func, ast.Name)):
            continue
        mapping[value.func.id] = target.attr
    return mapping


def _attach_client_attrs(entries: list[dict], client_map: dict[str, str]) -> None:
    """Mutate entries in place, adding `client_attr`. Falls back to the
    resource name when the client map is empty (no client_path configured)
    or the class isn't found there."""
    for entry in entries:
        cls = entry["class_name"]
        attr = client_map.get(cls) if client_map else None
        entry["client_attr"] = attr or entry["resource"].split(".")[-1]


def walk(sdk: _config.SdkConfig, target_files: Optional[list[str]] = None) -> dict:
    root = sdk.resolved_path
    if not root.is_dir():
        raise FileNotFoundError(f"SDK source not found: {root}")

    files: list[Path] = sorted(p for p in root.glob(sdk.resources_glob) if p.is_file())
    files = [p for p in files if p.suffix == ".py" and p.stem != "__init__"]

    if target_files is not None:
        wanted = set(target_files)
        files = [p for p in files if p.stem in wanted]

    if not files:
        return {"contract_version": CONTRACT_VERSION, "resources": []}

    client_map = build_client_attr_map(root, sdk.client_path)
    emitted: list[dict] = []
    for path in files:
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue
        rel_source = str(path.relative_to(root))
        match = _detect(path.stem, rel_source, tree, sdk.resource_base_classes)
        if not match:
            continue
        _attach_client_attrs(match, client_map)
        emitted.extend(match)
    return {"contract_version": CONTRACT_VERSION, "resources": emitted}


def main(argv: Optional[list[str]] = None) -> int:
    _ = argv
    cfg = _config.load()
    contract = walk(cfg.sdk)
    json.dump(contract, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
