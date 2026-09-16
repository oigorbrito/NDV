#!/usr/bin/env python3
"""NDV deterministic smoke for the inherited DV pilot harness.

This does not evaluate an LLM. It creates three fixture runs that exercise the
legacy harness end-to-end: expected NO, expected YES, expected NO.

Usage:
    python tools/ndv_deterministic_harness_smoke.py --legacy-dv-root ../dv
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

CASES = {
    "H0_NOOP": {"marker": None, "expected": "NO", "failure": "PRODUCT_FAILURE"},
    "H1_KNOWN_VALID": {"marker": "VALID", "expected": "YES", "failure": None},
    "H2_KNOWN_INVALID": {"marker": "INVALID", "expected": "NO", "failure": "PRODUCT_FAILURE"},
}


def write_fixture(root: Path, case_id: str) -> Path:
    case = CASES[case_id]
    executor = root / "executor.py"
    marker_expr = repr(case["marker"])
    executor.write_text(
        "import json, os, uuid\n"
        f"marker={marker_expr}\n"
        "if marker is not None:\n"
        "    open('candidate.marker','w',encoding='utf-8').write(marker+'\\n')\n"
        "event={'run_id':os.environ['DV_RUN_ID'],'event_id':str(uuid.uuid4()),"
        "'token_category':'execution','tokens':0,'monetary_cost':0.0,'currency':'USD',"
        "'source':'ndv-deterministic-fixture','provider':'fixture','model_or_service':'deterministic',"
        "'cache_status':'not_applicable','price_schedule_ref':'fixture-zero-cost-v1'}\n"
        "with open(os.environ['DV_EVENT_LOG'],'a',encoding='utf-8') as f:\n"
        "    f.write(json.dumps(event)+'\\n')\n",
        encoding="utf-8",
    )

    verifier = root / "verifier.py"
    expected = case["expected"]
    failure = case["failure"]
    verifier.write_text(
        "import json\n"
        "from pathlib import Path\n"
        "p=Path('candidate.marker')\n"
        "value=p.read_text(encoding='utf-8').strip() if p.exists() else None\n"
        f"expected={expected!r}\n"
        f"failure={failure!r}\n"
        "actual='YES' if value == 'VALID' else 'NO'\n"
        "result={'outcome':actual,'harness_valid':True,"
        "'evidence_refs':['fixture:candidate.marker' if p.exists() else 'fixture:no-marker'],"
        "'failure_attribution':None if actual == 'YES' else 'PRODUCT_FAILURE',"
        "'fixture_expected':expected}\n"
        "print(json.dumps(result))\n",
        encoding="utf-8",
    )

    spec = {
        "protocol_version": "NDV-P1-S1A-V1",
        "corpus_version": "DETERMINISTIC_FIXTURE_V1",
        "task_id": case_id,
        "task_family": "F1",
        "base_revision": "fixture",
        "oracle_version": "ndv-deterministic-oracle-v1",
        "treatment_id": "E0",
        "treatment_version": "deterministic-fixture-v1",
        "rollout_id": "r1",
        "environment_id": "ndv-deterministic-smoke",
        "working_directory": str(root),
        "executor_command": [sys.executable, str(executor)],
        "verifier_command": [sys.executable, str(verifier)],
        "executor_timeout_seconds": 5,
        "verifier_timeout_seconds": 5,
        "toolchain_versions": {"python": sys.version.split()[0]},
    }
    spec_path = root / "spec.json"
    spec_path.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return spec_path


def run_case(harness: Path, out_root: Path, case_id: str) -> dict:
    case_root = out_root / "fixtures" / case_id
    case_root.mkdir(parents=True)
    spec = write_fixture(case_root, case_id)
    runs = out_root / "runs"
    proc = subprocess.run(
        [sys.executable, str(harness), "run", "--spec", str(spec), "--out", str(runs)],
        text=True,
        capture_output=True,
        check=False,
    )
    run_dir_text = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
    run_dir = Path(run_dir_text) if run_dir_text else None
    result = {
        "case_id": case_id,
        "harness_exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "run_dir": str(run_dir) if run_dir else None,
        "pass": False,
        "errors": [],
    }
    if not run_dir or not run_dir.exists():
        result["errors"].append("harness did not produce a run directory")
        return result
    try:
        summary = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        reconciliation = json.loads((run_dir / "reconciliation.json").read_text(encoding="utf-8"))
    except Exception as exc:
        result["errors"].append(f"cannot read harness artifacts: {exc}")
        return result

    expected = CASES[case_id]
    verification = summary.get("verification", {})
    if reconciliation.get("status") != "PASS":
        result["errors"].append(f"reconciliation status is {reconciliation.get('status')}")
    if verification.get("outcome") != expected["expected"]:
        result["errors"].append(
            f"expected outcome {expected['expected']}, got {verification.get('outcome')}"
        )
    if verification.get("failure_attribution") != expected["failure"]:
        result["errors"].append(
            f"expected failure attribution {expected['failure']}, got {verification.get('failure_attribution')}"
        )
    if not verification.get("evidence_refs"):
        result["errors"].append("conclusive result has no evidence_refs")
    if reconciliation.get("recomputed", {}).get("total_system_tokens") != 0:
        result["errors"].append("fixture token telemetry did not reconcile to explicit zero")
    if reconciliation.get("recomputed", {}).get("total_monetary_cost") != 0.0:
        result["errors"].append("fixture monetary telemetry did not reconcile to explicit zero")
    result["pass"] = not result["errors"] and proc.returncode == 0
    result["verification"] = verification
    result["reconciliation"] = reconciliation
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy-dv-root", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    harness = (args.legacy_dv_root / "tools" / "dv_pilot_harness.py").resolve()
    if not harness.is_file():
        raise SystemExit(f"legacy harness not found: {harness}")

    if args.out:
        out_root = args.out.resolve()
        out_root.mkdir(parents=True, exist_ok=True)
        cleanup = None
    else:
        cleanup = tempfile.TemporaryDirectory(prefix="ndv-harness-smoke-")
        out_root = Path(cleanup.name)

    results = [run_case(harness, out_root, case_id) for case_id in CASES]
    report = {
        "campaign_id": "NDV-P1-S1A-DETERMINISTIC-HARNESS-SMOKE-V1",
        "legacy_harness": str(harness),
        "status": "PASS" if all(r["pass"] for r in results) else "FAIL",
        "cases": results,
    }
    report_path = out_root / "ndv-deterministic-harness-smoke-report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    if cleanup is not None:
        cleanup.cleanup()
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
