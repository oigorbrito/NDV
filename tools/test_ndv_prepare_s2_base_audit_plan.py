import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import ndv_prepare_s2_base_audit_plan as mod


def canonical_sha(value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def task_sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class BaseAuditPlanTests(unittest.TestCase):
    def make_fixture(self, root: Path):
        cid = "S2W01-org__repo-1"
        revision = "a" * 40
        statement = "fix the bug"
        row = {
            "instance_id": "org__repo-1",
            "repo": "org/repo",
            "base_commit": revision,
            "problem_statement": statement,
            "install_config": {"test_cmd": "pytest -q", "log_parser": "pytest"},
        }
        task = {
            "instance_id": row["instance_id"],
            "repo": row["repo"],
            "base_commit": revision,
            "problem_statement": statement,
            "language": "python",
        }
        raw_sha = canonical_sha(row)
        projection_sha = canonical_sha(task)
        statement_sha = task_sha(statement)

        wave = root / "wave.json"
        wave_payload = {
            "schema_id": "ndv-p1-s2-candidate-wave-v1",
            "wave_id": "W1",
            "candidates": [{
                "candidate_id": cid,
                "source_instance_id": row["instance_id"],
                "source_row_index": 7,
                "repository": row["repo"],
                "base_revision": revision,
                "language": "python",
                "image_ref": "docker.io/example/repo:1",
            }],
        }
        wave.write_text(json.dumps(wave_payload), encoding="utf-8")

        qdir = root / "quarantine" / cid
        qdir.mkdir(parents=True)
        admission = qdir / "admission-only.json"
        admission_payload = {
            "schema_id": "ndv-p1-s2-admission-only-row-v1",
            "candidate_id": cid,
            "source": {
                "source_instance_id": row["instance_id"],
                "source_row_index": 7,
                "ndv_canonical_row_sha256": raw_sha,
            },
            "full_row": row,
        }
        admission.write_text(json.dumps(admission_payload), encoding="utf-8")
        executor = qdir / "executor-visible.json"
        executor_payload = {
            "schema_id": "ndv-p1-s2-executor-visible-row-v1",
            "candidate_id": cid,
            "source_binding": {
                "dataset_revision": "b" * 40,
                "source_row_index": 7,
                "ndv_canonical_row_sha256": raw_sha,
            },
            "task_statement_sha256": statement_sha,
            "executor_visible_sha256": projection_sha,
            "task": task,
        }
        executor.write_text(json.dumps(executor_payload), encoding="utf-8")

        aggregate = root / "quarantine" / "quarantine-aggregate.json"
        aggregate_payload = {
            "schema_id": "ndv-p1-s2-quarantine-aggregate-v2",
            "wave_id": "W1",
            "candidate_count": 1,
            "passed_count": 1,
            "manifests": [{
                "candidate_id": cid,
                "status": "PASS",
                "source_row_index": 7,
                "source_instance_id": row["instance_id"],
                "ndv_canonical_row_sha256": raw_sha,
                "task_statement_sha256": statement_sha,
                "executor_visible_sha256": projection_sha,
                "admission_only_ref": str(admission.resolve()),
                "executor_visible_ref": str(executor.resolve()),
                "treatment_execution": "NOT_EXECUTED",
                "holdout_access": "NONE",
            }],
        }
        aggregate.write_text(json.dumps(aggregate_payload), encoding="utf-8")

        receipt = root / "materialization-receipt.json"
        receipt_payload = {
            "schema_id": "ndv-p1-s2-wave-materialization-receipt-v2",
            "status": "MATERIALIZED_QUARANTINED",
            "wave_id": "W1",
            "wave_file_sha256": mod.sha256_file(wave),
            "quarantine_aggregate_ref": str(aggregate.resolve()),
            "quarantine_aggregate_file_sha256": mod.sha256_file(aggregate),
            "candidate_count": 1,
            "passed_count": 1,
            "docker_execution": False,
            "model_execution": "NONE",
            "treatment_execution": "NOT_EXECUTED",
            "holdout_access": "NONE",
        }
        receipt.write_text(json.dumps(receipt_payload), encoding="utf-8")
        return receipt, wave, admission, executor, aggregate

    def test_valid_materialization_builds_one_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipt, wave, *_ = self.make_fixture(root)
            plan = mod.build_plan(receipt, wave, root / "audits", root / "runner.py")
            self.assertEqual(plan["status"], "AUDIT_PLAN_READY")
            self.assertEqual(plan["candidate_count"], 1)
            entry = plan["entries"][0]
            self.assertEqual(entry["candidate_id"], "S2W01-org__repo-1")
            self.assertEqual(entry["authorized_action"], "PRE_SOLUTION_BASE_AUDIT_ONLY")
            self.assertIsNone(entry["image_digest"])
            self.assertEqual(plan["treatment_execution"], "NOT_EXECUTED")

    def test_tampered_admission_full_row_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipt, wave, admission, *_ = self.make_fixture(root)
            payload = json.loads(admission.read_text())
            payload["full_row"]["problem_statement"] = "tampered"
            admission.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "raw row hash binding"):
                mod.build_plan(receipt, wave, root / "audits", root / "runner.py")

    def test_tampered_executor_projection_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipt, wave, _, executor, _ = self.make_fixture(root)
            payload = json.loads(executor.read_text())
            payload["task"]["language"] = "rust"
            executor.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "executor projection hash"):
                mod.build_plan(receipt, wave, root / "audits", root / "runner.py")

    def test_contaminated_receipt_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipt, wave, *_ = self.make_fixture(root)
            payload = json.loads(receipt.read_text())
            payload["treatment_execution"] = "EXECUTED"
            receipt.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "contaminated"):
                mod.build_plan(receipt, wave, root / "audits", root / "runner.py")

    def test_candidate_set_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipt, wave, _, _, aggregate = self.make_fixture(root)
            q = json.loads(aggregate.read_text())
            q["manifests"][0]["candidate_id"] = "wrong"
            aggregate.write_text(json.dumps(q), encoding="utf-8")
            r = json.loads(receipt.read_text())
            r["quarantine_aggregate_file_sha256"] = mod.sha256_file(aggregate)
            receipt.write_text(json.dumps(r), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "candidate set mismatch"):
                mod.build_plan(receipt, wave, root / "audits", root / "runner.py")


if __name__ == "__main__":
    unittest.main()
