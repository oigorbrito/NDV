import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ndv_run_s2_base_audit as audit


class BaseAuditTests(unittest.TestCase):
    def candidate(self):
        return {
            "candidate_id": "S2W01-example",
            "source_instance_id": "example__repo-1",
            "repository": "example/repo",
            "base_revision": "a" * 40,
            "image_ref": "registry.example/repo:tag",
        }

    def row(self):
        return {
            "instance_id": "example__repo-1",
            "repo": "example/repo",
            "base_commit": "a" * 40,
            "install_config": {
                "test_cmd": ["pytest -q"],
                "log_parser": "parse_pytest",
            },
            "patch": "GOLD SOLUTION",
            "test_patch": "GOLD TEST PATCH",
        }

    def test_identity_mismatch_blocks_before_execution(self):
        row = self.row()
        row["base_commit"] = "b" * 40
        errors, *_ = audit.validate_row(row, self.candidate())
        self.assertTrue(any("base_commit mismatch" in e for e in errors))

    def test_commands_come_only_from_test_cmd(self):
        row = self.row()
        errors, image, workdir, commands, parser = audit.validate_row(row, self.candidate())
        self.assertEqual(errors, [])
        self.assertEqual(commands, ["pytest -q"])
        self.assertEqual(parser, "parse_pytest")
        self.assertNotIn("GOLD SOLUTION", "\n".join(commands))
        self.assertNotIn("GOLD TEST PATCH", "\n".join(commands))
        self.assertEqual(workdir, "/repo")
        self.assertEqual(image, "registry.example/repo:tag")

    @patch("ndv_run_s2_base_audit.run")
    def test_execute_base_never_applies_patch(self, mocked_run):
        class Result:
            returncode = 1
            stdout = "tests failed"
            stderr = ""
        mocked_run.return_value = Result()
        result = audit.execute_base(
            "registry.example/repo@sha256:" + "1" * 64,
            "/repo",
            ["pytest -q"],
            10,
        )
        argv = result["argv"]
        shell_script = argv[-1]
        self.assertIn("pytest -q", shell_script)
        self.assertNotIn("git apply", shell_script)
        self.assertNotIn("patch.diff", shell_script)
        self.assertNotIn("test_patch.diff", shell_script)
        self.assertEqual(result["returncode"], 1)

    @patch("ndv_run_s2_base_audit.run")
    def test_digest_resolution_requires_rep_digest(self, mocked_run):
        class Result:
            returncode = 0
            stdout = "[]"
            stderr = ""
        mocked_run.return_value = Result()
        with self.assertRaises(RuntimeError):
            audit.resolve_image_digest("registry.example/repo:tag")


if __name__ == "__main__":
    unittest.main()
