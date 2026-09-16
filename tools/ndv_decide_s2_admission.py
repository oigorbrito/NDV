#!/usr/bin/env python3
"""Produce deterministic NDV S2 admission decisions from frozen wave + audit evidence.

This tool never executes treatments and never upgrades evidence. It only decides
whether the already-recorded gates are sufficient to admit a candidate.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def index_by(items: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in items:
        value = item.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError(f"missing {key}")
        if value in out:
            raise ValueError(f"duplicate {key}: {value}")
        out[value] = item
    return out


def decide_candidate(candidate: dict[str, Any], audit: dict[str, Any] | None) -> dict[str, Any]:
    cid = candidate["candidate_id"]
    blockers: list[str] = []
    if candidate.get("quarantine_status") != "PASS":
        blockers.append("QUARANTINE_NOT_PASS")
    if audit is None:
        blockers.append("AUDIT_RECORD_MISSING")
    else:
        if audit.get("status") != "AUDIT_PASS":
            blockers.append(f"AUDIT_STATUS_{audit.get('status', 'MISSING')}")
        if audit.get("oracle_classification") != "EXPECTED_BASE_BEHAVIOR":
            blockers.append("BASE_ORACLE_NOT_EXPECTED")
        if audit.get("verifier_independent") is not True:
            blockers.append("VERIFIER_INDEPENDENCE_NOT_PROVEN")
        if audit.get("preservation_baseline_pass") is not True:
            blockers.append("PRESERVATION_NOT_PASS")
        if audit.get("treatment_execution") != "NOT_EXECUTED":
            blockers.append("TREATMENT_EXECUTION_CONTAMINATION")
    if candidate.get("proposed_family") in {None, "", "UNASSIGNED_PENDING_SCREEN"}:
        blockers.append("FAMILY_UNASSIGNED")
    if candidate.get("solution_isolation") not in {"PASS", "PROVEN"}:
        blockers.append("SOLUTION_ISOLATION_NOT_PROVEN")

    return {
        "candidate_id": cid,
        "decision": "ADMIT" if not blockers else "DO_NOT_ADMIT",
        "blockers": blockers,
        "evidence_refs": {
            "quarantine_manifest_ref": candidate.get("quarantine_manifest_ref"),
            "base_run_ref": None if audit is None else audit.get("base_run_ref"),
            "oracle_interpretation_ref": None if audit is None else audit.get("oracle_interpretation_ref"),
            "focal_verifier_ref": None if audit is None else audit.get("focal_verifier_ref"),
            "preservation_ref": None if audit is None else audit.get("preservation_ref"),
            "verifier_provenance_ref": None if audit is None else audit.get("verifier_provenance_ref"),
            "environment_ref": None if audit is None else audit.get("environment_ref"),
        },
    }


def decide(wave: dict[str, Any], audit_state: dict[str, Any]) -> dict[str, Any]:
    candidates = wave.get("candidates")
    audits = audit_state.get("audits")
    if not isinstance(candidates, list) or not isinstance(audits, list):
        raise ValueError("wave.candidates and audit_state.audits must be arrays")
    audit_index = index_by(audits, "candidate_id")
    decisions = [decide_candidate(c, audit_index.get(c.get("candidate_id"))) for c in candidates]
    return {
        "schema_id": "ndv-p1-s2-admission-decisions-v1",
        "wave_id": wave.get("wave_id"),
        "treatment_execution": "NOT_EXECUTED",
        "decisions": decisions,
        "summary": {
            "candidate_count": len(decisions),
            "admit_count": sum(d["decision"] == "ADMIT" for d in decisions),
            "do_not_admit_count": sum(d["decision"] == "DO_NOT_ADMIT" for d in decisions),
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--wave", required=True, type=Path)
    ap.add_argument("--audit", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    wave = load(args.wave)
    audit = load(args.audit)
    result = decide(wave, audit)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
