import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ndv_acquire_s2_images as mod


class ImageAcquisitionTests(unittest.TestCase):
    def test_repository_of_strips_tag_not_registry_port(self):
        self.assertEqual(mod.repository_of("docker.io/org/repo:tag"), "docker.io/org/repo")
        self.assertEqual(mod.repository_of("localhost:5000/org/repo:tag"), "localhost:5000/org/repo")

    @mock.patch.object(mod, "run")
    def test_resolve_digest_requires_same_repository(self, run_mock):
        class P:
            returncode = 0
            stdout = json.dumps(["docker.io/other/repo@sha256:" + "1" * 64, "docker.io/org/repo@sha256:" + "2" * 64])
            stderr = ""
        run_mock.return_value = P()
        self.assertEqual(mod.resolve_digest("docker.io/org/repo:tag"), "docker.io/org/repo@sha256:" + "2" * 64)

    @mock.patch.object(mod, "run")
    def test_resolve_digest_rejects_ambiguity(self, run_mock):
        class P:
            returncode = 0
            stdout = json.dumps(["docker.io/org/repo@sha256:" + "1" * 64, "docker.io/org/repo@sha256:" + "2" * 64])
            stderr = ""
        run_mock.return_value = P()
        with self.assertRaisesRegex(RuntimeError, "exactly one RepoDigest"):
            mod.resolve_digest("docker.io/org/repo:tag")

    def test_wave_contamination_blocks_before_pull(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wave = root / "wave.json"
            wave.write_text(json.dumps({"schema_id":"ndv-p1-s2-candidate-wave-v1","wave_id":"w","wave_summary":{"treatment_execution":"EXECUTED","holdout_access":"NONE"},"candidates":[{"image_ref":"docker.io/org/repo:tag"}]}))
            out = root / "out.json"
            with mock.patch("sys.argv", ["prog", "--wave", str(wave), "--out", str(out)]), self.assertRaises(SystemExit):
                mod.main()

    @mock.patch.object(mod, "resolve_digest")
    @mock.patch.object(mod, "run")
    def test_happy_path_records_immutable_digest(self, run_mock, digest_mock):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wave = root / "wave.json"
            wave.write_text(json.dumps({"schema_id":"ndv-p1-s2-candidate-wave-v1","wave_id":"w","wave_summary":{"treatment_execution":"NOT_EXECUTED","holdout_access":"NONE"},"candidates":[{"image_ref":"docker.io/org/repo:tag"}]}))
            class P: returncode = 0; stdout = "ok"; stderr = ""
            run_mock.return_value = P(); digest_mock.return_value = "docker.io/org/repo@sha256:" + "a"*64
            out = root / "receipt.json"
            with mock.patch("sys.argv", ["prog", "--wave", str(wave), "--out", str(out)]):
                self.assertEqual(mod.main(), 0)
            receipt = json.loads(out.read_text())
            self.assertEqual(receipt["status"], "IMAGES_ACQUIRED_AND_PINNED")
            self.assertEqual(receipt["images"][0]["repo_digest"], "docker.io/org/repo@sha256:" + "a"*64)
            self.assertFalse(receipt["container_execution"])
            self.assertEqual(receipt["treatment_execution"], "NOT_EXECUTED")


if __name__ == "__main__": unittest.main()
