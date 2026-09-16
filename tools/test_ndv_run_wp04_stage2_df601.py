import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ndv_run_wp04_stage2_df601 as mod


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Stage2GateTests(unittest.TestCase):
    def make_import(self, *, schema="ndv-wp04-import-manifest-v2", binding_id="B1", sidecar=False) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        evidence = root / "evidence"
        evidence.mkdir()
        candidate = b""
        executor = b"Tokens: 1k sent, 2 received.\n"
        report = {
            "schema_id": "ndv-wp04-stage1-run-v1",
            "task_id": "D-F5-01",
            "binding_id": binding_id,
            "outcome": "SMOKE_VALID_FAILED",
        }
        report_bytes = (json.dumps(report, sort_keys=True) + "\n").encode()
        (root / "run-report.json").write_bytes(report_bytes)
        (evidence / "candidate.diff").write_bytes(candidate)
        (evidence / "executor.log").write_bytes(executor)
        manifest = {
            "schema_id": schema,
            "task_id": "D-F5-01",
            "binding_id": binding_id,
            "outcome": "SMOKE_VALID_FAILED",
            "raw_evidence_preserved": True,
            "treatment_reexecuted": False,
            "candidate_diff_sha256": sha(candidate),
            "preserved_artifacts": [
                {"path": "run-report.json", "sha256": sha(report_bytes), "size_bytes": len(report_bytes)},
                {"path": "evidence/candidate.diff", "sha256": sha(candidate), "size_bytes": len(candidate)},
                {"path": "evidence/executor.log", "sha256": sha(executor), "size_bytes": len(executor)},
            ],
        }
        name = "import-manifest-v2.json" if sidecar else "import-manifest.json"
        (root / name).write_text(json.dumps(manifest), encoding="utf-8")
        if sidecar:
            (root / "import-manifest.json").write_text(json.dumps({"schema_id": "ndv-wp04-import-manifest-v1"}), encoding="utf-8")
        return root

    def test_valid_import_passes(self):
        root = self.make_import()
        manifest = mod.validate_stage1_import(root, "B1")
        self.assertEqual(manifest["task_id"], "D-F5-01")

    def test_v2_sidecar_supersedes_legacy_manifest(self):
        root = self.make_import(sidecar=True)
        manifest = mod.validate_stage1_import(root, "B1")
        self.assertEqual(manifest["schema_id"], "ndv-wp04-import-manifest-v2")

    def test_old_manifest_is_rejected_without_sidecar(self):
        root = self.make_import(schema="ndv-wp04-import-manifest-v1")
        with self.assertRaises(ValueError):
            mod.validate_stage1_import(root, "B1")

    def test_binding_mismatch_is_rejected(self):
        root = self.make_import(binding_id="B1")
        with self.assertRaises(ValueError):
            mod.validate_stage1_import(root, "B2")

    def test_tampered_evidence_is_rejected(self):
        root = self.make_import()
        (root / "evidence" / "executor.log").write_text("tampered", encoding="utf-8")
        with self.assertRaises(ValueError):
            mod.validate_stage1_import(root, "B1")

    def test_dict_shaped_v2_inventory_is_rejected(self):
        root = self.make_import()
        path = root / "import-manifest.json"
        manifest = json.loads(path.read_text())
        manifest["preserved_artifacts"] = {"run-report.json": {"sha256": "a" * 64, "bytes": 1}}
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "canonical v2 list form"):
            mod.validate_stage1_import(root, "B1")

    def test_explicit_aider_must_match_frozen_binding_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frozen = root / "aider.exe"; frozen.write_text("x")
            other = root / "other.exe"; other.write_text("x")
            binding = {"scaffold": {"executable_path": str(frozen)}}
            with self.assertRaisesRegex(ValueError, "differs from frozen"):
                mod.resolve_frozen_aider(binding, other)
            self.assertEqual(Path(mod.resolve_frozen_aider(binding, frozen)), frozen.resolve())

    @mock.patch.object(mod, "run")
    def test_aider_version_must_match_binding(self, run_mock):
        class P:
            returncode = 0
            stdout = "aider 0.86.2\n"
            stderr = ""
        run_mock.return_value = P()
        binding = {"scaffold": {"version_or_commit": "aider 0.86.2"}}
        self.assertEqual(mod.validate_aider_version("aider.exe", binding), "aider 0.86.2")
        binding["scaffold"]["version_or_commit"] = "aider 0.99.0"
        with self.assertRaisesRegex(ValueError, "version mismatch"):
            mod.validate_aider_version("aider.exe", binding)


if __name__ == "__main__":
    unittest.main()
