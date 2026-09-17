import json
import tempfile
import unittest
from pathlib import Path

import ndv_wp07_codex_bundle as mod


class CodexBundleTests(unittest.TestCase):
    def make_bundle(self, root: Path) -> Path:
        d = root / "bundle"; (d / "evidence").mkdir(parents=True)
        q = {"schema_id":"ndv-p1-wp07-codex-subscription-qualification-v1","status":"S0_READY","candidate_id":"C","requested_model":"gpt-5.6-sol"}
        qp = d / "qualification.json"; qp.write_text(json.dumps(q), encoding="utf-8")
        b = {"schema_id":"ndv-p1-wp07-executor-binding-v1","status":"QUALIFIED","binding_id":"B","candidate_id":"C","model":{"identity":"gpt-5.6-sol"},"qualification_file_sha256":mod.sha_file(qp)}
        (d / "executor-binding.json").write_text(json.dumps(b), encoding="utf-8")
        (d / "evidence" / "executor.log").write_text("model: gpt-5.6-sol\n", encoding="utf-8")
        (d / "evidence" / "candidate.diff").write_bytes(b"diff\n")
        (d / "evidence" / "git-status.txt").write_text(" M TARGET.txt\n", encoding="utf-8")
        mod.seal_bundle(d)
        return d

    def test_sealed_bundle_verifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = self.make_bundle(Path(tmp))
            out = mod.verify_bundle(d, expected_model="gpt-5.6-sol", expected_candidate="C")
            self.assertEqual(out["manifest"]["status"], "SEALED_SYNTHETIC_QUALIFICATION_EVIDENCE")

    def test_tampered_diff_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = self.make_bundle(Path(tmp)); (d / "evidence" / "candidate.diff").write_text("tampered", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash/size mismatch"):
                mod.verify_bundle(d)

    def test_tampered_executor_log_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = self.make_bundle(Path(tmp)); (d / "evidence" / "executor.log").write_text("tampered", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash/size mismatch"):
                mod.verify_bundle(d)

    def test_missing_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = self.make_bundle(Path(tmp)); (d / "evidence-manifest.json").unlink()
            with self.assertRaisesRegex(ValueError, "required"):
                mod.verify_bundle(d)


if __name__ == "__main__": unittest.main()
