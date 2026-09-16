import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODULE_PATH = HERE / "ndv_quarantine_swe_rebench_rows.py"
spec = importlib.util.spec_from_file_location("ndv_quarantine", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


class QuarantineTests(unittest.TestCase):
    def candidate(self):
        return {"candidate_id": "S2W01-fixture", "source_instance_id": "owner__repo-1", "source_row_index": 12, "source_record_sha256": "a" * 64, "repository": "owner/repo", "base_revision": "b" * 40}

    def wave(self):
        return {"source": {"dataset": "fixture/dataset", "split": "train", "dataset_revision": "c" * 40}}

    def row(self):
        return {"instance_id": "owner__repo-1", "repo": "owner/repo", "base_commit": "b" * 40, "problem_statement": "Fix the deterministic fixture bug.", "language": "python", "patch": "SECRET GOLD PATCH", "test_patch": "SECRET TEST PATCH", "FAIL_TO_PASS": ["test_bug"], "PASS_TO_PASS": ["test_other"], "meta": {"gold": True}, "install_config": {"cmd": "secret"}, "pr_description": "may contain solution hints", "future_upstream_field": "must remain admission-only by default"}

    def test_projection_is_strict_allowlist(self):
        projected = module.project_executor_view(self.row())
        self.assertEqual(set(projected), set(module.EXECUTOR_ALLOWLIST))
        for forbidden in module.FORBIDDEN_EXECUTOR_FIELDS:
            self.assertNotIn(forbidden, projected)
        self.assertNotIn("future_upstream_field", projected)

    def test_quarantine_binds_two_views_and_keeps_gold_admission_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = module.quarantine_one(self.row(), 12, self.candidate(), self.wave(), root, "fixture.json")
            self.assertEqual(manifest["status"], "PASS")
            self.assertEqual(manifest["source_row_index"], 12)
            self.assertFalse(manifest["raw_row_mutated"])
            admission = json.loads((root / "S2W01-fixture" / "admission-only.json").read_text())
            executor = json.loads((root / "S2W01-fixture" / "executor-visible.json").read_text())
            self.assertEqual(admission["full_row"]["patch"], "SECRET GOLD PATCH")
            self.assertNotIn("patch", executor["task"])
            self.assertNotIn("future_upstream_field", executor["task"])
            self.assertEqual(executor["source_binding"]["source_row_index"], 12)

    def test_identity_mismatch_is_rejected(self):
        row = self.row(); row["base_commit"] = "d" * 40
        with self.assertRaises(ValueError):
            module.validate_identity(row, self.candidate())

    def test_find_row_requires_unique_instance_and_original_index_match(self):
        candidate = self.candidate(); row = self.row()
        idx, found = module.find_row([(12, row)], candidate)
        self.assertEqual(idx, 12)
        self.assertEqual(found["instance_id"], candidate["source_instance_id"])
        with self.assertRaises(ValueError):
            module.find_row([(12, row), (13, dict(row))], candidate)
        with self.assertRaises(ValueError):
            module.find_row([(0, row)], candidate)


if __name__ == "__main__":
    unittest.main()
