#!/usr/bin/env python3
"""Independent structural verifier for D-F5-01.

This verifier encodes requirement-level invariants from the pre-solution issue,
not the historical solution diff. It is intentionally external to the executor
workspace and is never included in the executor prompt.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any


def parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def function_names(tree: ast.Module) -> set[str]:
    return {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def calls_named(tree: ast.AST, name: str) -> int:
    total = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == name:
            total += 1
        elif isinstance(func, ast.Attribute) and func.attr == name:
            total += 1
    return total


def imports_name(tree: ast.Module, name: str) -> bool:
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            if any(alias.name == name for alias in node.names):
                return True
    return False


def doctor_precedes_persistence(cli_tree: ast.Module) -> bool:
    main = next((n for n in cli_tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"), None)
    if main is None:
        return False
    doctor_idx = None
    persistence_idx = None
    for idx, stmt in enumerate(main.body):
        text = ast.dump(stmt, include_attributes=False)
        if doctor_idx is None and "doctor" in text and "run_doctor" in text:
            doctor_idx = idx
        if persistence_idx is None and any(x in text for x in ("SQLiteMissionStore", "SQLiteEventLedger", "SQLiteExecutionHandleStore")):
            persistence_idx = idx
    return doctor_idx is not None and persistence_idx is not None and doctor_idx < persistence_idx


def verify(workspace: Path) -> dict[str, Any]:
    cli_path = workspace / "src" / "metao" / "cli.py"
    doctor_path = workspace / "src" / "metao" / "doctor.py"
    entry_path = workspace / "src" / "metao" / "entrypoint.py"
    missing = [str(p) for p in (cli_path, doctor_path, entry_path) if not p.is_file()]
    if missing:
        return {"status": "FAIL", "reason": "missing source files", "missing": missing, "checks": {}}

    cli = parse(cli_path)
    doctor = parse(doctor_path)
    entry = parse(entry_path)
    checks = {
        "canonical_loader_defined": "load_factory_callable" in function_names(cli),
        "mission_cli_reuses_loader": calls_named(cli, "load_factory_callable") >= 1,
        "doctor_reuses_loader": imports_name(doctor, "load_factory_callable") and calls_named(doctor, "load_factory_callable") >= 1,
        "runtime_entrypoint_reuses_loader": imports_name(entry, "load_factory_callable") and calls_named(entry, "load_factory_callable") >= 1,
        "doctor_precedes_persistence_wiring": doctor_precedes_persistence(cli),
    }
    return {
        "schema_id": "ndv-d-f5-01-structural-verifier-v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workspace", required=True, type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    result = verify(args.workspace.resolve())
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if result.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
