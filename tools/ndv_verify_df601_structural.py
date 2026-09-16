#!/usr/bin/env python3
"""External structural verifier for D-F6-01.

This verifier is not shown to the executor. It checks requirement-level
invariants needed to distinguish the untouched base from a relevant candidate.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def check(workspace: Path) -> dict[str, bool]:
    persistence = workspace / "experiments/rust-chassis-a/metao-contracts/tests/discovery_persistence_tests.rs"
    shadow = workspace / "experiments/rust-chassis-a/metao-testkit/tests/phase6_shadow.rs"
    p = persistence.read_text(encoding="utf-8")
    s = shadow.read_text(encoding="utf-8")
    return {
        "parallel_temp_store_has_monotonic_process_local_component": (
            "AtomicU64" in p and "fetch_add" in p and "process::id" in p
        ),
        "external_cargo_target_dir_honored": (
            "CARGO_TARGET_DIR" in s and "var_os" in s and "target_root" in s
        ),
        "cargo_bin_exe_remains_first_authority": (
            "CARGO_BIN_EXE_metao-wire-runtime" in s
            and s.find("CARGO_BIN_EXE_metao-wire-runtime") < s.find("CARGO_TARGET_DIR")
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workspace", required=True, type=Path)
    args = ap.parse_args()
    checks = check(args.workspace.resolve())
    status = "PASS" if all(checks.values()) else "FAIL"
    print(json.dumps({"schema_id": "ndv-d-f6-01-structural-verifier-v1", "status": status, "checks": checks}, indent=2))
    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
