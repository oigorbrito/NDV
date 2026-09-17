import json
import tempfile
import unittest
from pathlib import Path

import ndv_assess_s2_corpus_readiness as mod


class CorpusReadinessTests(unittest.TestCase):
    def fixtures(self, root: Path):
        intake = root / "intake.json"
        intake.write_text(json.dumps({
            "schema_id": "ndv-p1-s2-corpus-intake-v1",
            "historical_normative_corpus": {"corpus_id": "p1-development-corpus-v6"},
            "target": {"initial_admitted_tasks": 9, "minimum_families": 3, "minimum_repositories": 3, "minimum_languages": 2},
        }))
        legacy = root / "legacy.json"
        legacy.write_text(json.dumps({
            "schema_id": "ndv-dv-legacy-manifest-v1",
            "normative_historical_p1_corpus": {"corpus_id": "p1-development-corpus-v6", "counts": {"tasks": 4, "families": 3, "repositories": 3}},
        }))
        return intake, legacy

    def record(self, root: Path, i: int, language: str = "python") -> Path:
        payload = {
            "schema_id": "ndv-p1-s2-admission-record-v2",
            "candidate_id": f"C{i}", "source_instance_id": f"I{i}", "repository": f"org/r{i}",
            "base_revision": "a" * 40, "language": language, "family": "F2",
            "selection": {"treatment_performance_consulted": False, "treatment_execution_before_admission": False, "holdout_access": "NONE"},
            "status": "ADMITTED_FROZEN",
        }
        payload["record_sha256"] = mod.sha(payload)
        path = root / f"r{i}.json"; path.write_text(json.dumps(payload))
        return path

    def test_five_s2_records_and_two_languages_reach_target_without_releasing_wp07(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); intake, legacy = self.fixtures(root)
            records = [self.record(root, i, "python" if i < 4 else "rust") for i in range(5)]
            result = mod.assess(intake, legacy, records)
            self.assertEqual(result["status"], "WP06_INTAKE_TARGET_REACHED")
            self.assertEqual(result["combined_task_count"], 9)
            self.assertEqual(result["comparative_corpus_ready"], "NO")
            self.assertEqual(result["wp07_release"], "NO")

    def test_four_s2_records_do_not_reach_task_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); intake, legacy = self.fixtures(root)
            records = [self.record(root, i, "python" if i < 3 else "rust") for i in range(4)]
            result = mod.assess(intake, legacy, records)
            self.assertEqual(result["status"], "WP06_INTAKE_TARGET_NOT_REACHED")
            self.assertFalse(result["checks"]["task_target"])

    def test_language_minimum_is_proven_conservatively_from_s2(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); intake, legacy = self.fixtures(root)
            records = [self.record(root, i, "python") for i in range(5)]
            result = mod.assess(intake, legacy, records)
            self.assertEqual(result["status"], "WP06_INTAKE_TARGET_NOT_REACHED")
            self.assertFalse(result["checks"]["language_minimum_demonstrated_by_s2"])

    def test_tampered_record_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); intake, legacy = self.fixtures(root)
            record = self.record(root, 1)
            payload = json.loads(record.read_text()); payload["language"] = "rust"; record.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "record_sha256 mismatch"):
                mod.assess(intake, legacy, [record])

    def test_duplicate_source_instance_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); intake, legacy = self.fixtures(root)
            a, b = self.record(root, 1), self.record(root, 2)
            payload = json.loads(b.read_text()); payload["source_instance_id"] = "I1"; payload["record_sha256"] = mod.sha({k:v for k,v in payload.items() if k != "record_sha256"}); b.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "duplicate S2"):
                mod.assess(intake, legacy, [a, b])


if __name__ == "__main__":
    unittest.main()
