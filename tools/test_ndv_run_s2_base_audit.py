import unittest
from unittest.mock import patch

import ndv_run_s2_base_audit as audit


class BaseAuditTests(unittest.TestCase):
    def candidate(self):
        return {
            "candidate_id": "S2W01-example",
            "source_instance_id": "example__repo-1",
            "source_row_index": 12,
            "repository": "example/repo",
            "base_revision": "a" * 40,
            "image_ref": "registry.example/repo:tag",
        }

    def row(self):
        return {
            "instance_id": "example__repo-1",
            "repo": "example/repo",
            "base_commit": "a" * 40,
            "install_config": {"test_cmd": ["false", "true"], "log_parser": "parse_pytest"},
            "patch": "GOLD SOLUTION",
            "test_patch": "GOLD TEST PATCH",
        }

    def artifact(self):
        row = self.row()
        return {
            "schema_id": "ndv-p1-s2-admission-only-row-v1",
            "candidate_id": "S2W01-example",
            "source": {
                "source_instance_id": "example__repo-1",
                "source_row_index": 12,
                "ndv_canonical_row_sha256": audit.sha256_bytes(audit.canonical_bytes(row)),
            },
            "full_row": row,
        }

    def test_unwrap_revalidates_raw_row_hash(self):
        artifact = self.artifact()
        self.assertEqual(audit.unwrap_admission_artifact(artifact, self.candidate()), self.row())
        artifact["full_row"]["repo"] = "tampered/repo"
        with self.assertRaises(ValueError):
            audit.unwrap_admission_artifact(artifact, self.candidate())

    def test_identity_mismatch_blocks_before_execution(self):
        row = self.row()
        row["base_commit"] = "b" * 40
        errors, *_ = audit.validate_row(row, self.candidate())
        self.assertTrue(any("base_commit mismatch" in e for e in errors))

    def test_commands_come_only_from_test_cmd(self):
        errors, image, workdir, commands, parser = audit.validate_row(self.row(), self.candidate())
        self.assertEqual(errors, [])
        self.assertEqual(commands, ["false", "true"])
        self.assertEqual(parser, "parse_pytest")
        self.assertNotIn("GOLD SOLUTION", "\n".join(commands))
        self.assertNotIn("GOLD TEST PATCH", "\n".join(commands))
        self.assertEqual(workdir, "/repo")
        self.assertEqual(image, "registry.example/repo:tag")

    def test_script_proves_head_cleanliness_and_every_command(self):
        script = audit.build_script("a" * 40, ["false", "true"])
        self.assertIn("__NDV_HEAD__", script)
        self.assertIn("__NDV_CLEAN__", script)
        self.assertIn("__NDV_CMD_1_RC__", script)
        self.assertIn("__NDV_CMD_2_RC__", script)
        self.assertNotIn("git apply", script)

    def test_marker_parser_preserves_earlier_failure(self):
        text = "__NDV_HEAD__=" + "a" * 40 + "\n__NDV_CLEAN__=YES\n__NDV_CMD_1_RC__=1\n__NDV_CMD_2_RC__=0\n"
        parsed = audit.parse_execution_markers(text, 2)
        self.assertEqual(parsed["command_returncodes"], [1, 0])
        self.assertTrue(parsed["all_command_markers_present"])
        self.assertTrue(parsed["clean_before_tests"])

    @patch("ndv_run_s2_base_audit.run")
    def test_execute_base_never_applies_patch(self, mocked_run):
        class Result:
            returncode = 1
            stdout = "__NDV_HEAD__=" + "a" * 40 + "\n__NDV_CLEAN__=YES\n__NDV_CMD_1_RC__=1\n"
            stderr = ""
        mocked_run.return_value = Result()
        result = audit.execute_base("registry.example/repo@sha256:" + "1" * 64, "/repo", "a" * 40, ["pytest -q"], 10)
        shell_script = result["argv"][-1]
        self.assertIn("pytest -q", shell_script)
        self.assertNotIn("git apply", shell_script)
        self.assertEqual(result["returncode"], 1)

    def test_image_repository_normalization(self):
        self.assertEqual(audit.normalize_image_repository("docker.io/swerebenchv2/foo:tag"), "swerebenchv2/foo")
        self.assertEqual(audit.normalize_image_repository("swerebenchv2/foo@sha256:" + "1" * 64), "swerebenchv2/foo")
        self.assertEqual(audit.normalize_image_repository("registry.example:5000/org/repo:tag"), "registry.example:5000/org/repo")

    def test_repo_digest_match_uses_same_repository(self):
        self.assertTrue(audit.repo_digest_matches_image_ref(
            "swerebenchv2/foo@sha256:" + "1" * 64,
            "docker.io/swerebenchv2/foo:tag",
        ))
        self.assertFalse(audit.repo_digest_matches_image_ref(
            "other/foo@sha256:" + "1" * 64,
            "docker.io/swerebenchv2/foo:tag",
        ))

    @patch("ndv_run_s2_base_audit.run")
    def test_digest_resolution_requires_repo_digest(self, mocked_run):
        class Result:
            returncode = 0
            stdout = "[]"
            stderr = ""
        mocked_run.return_value = Result()
        with self.assertRaises(RuntimeError):
            audit.resolve_image_digest("registry.example/repo:tag")

    @patch("ndv_run_s2_base_audit.run")
    def test_digest_resolution_ignores_unrelated_alias(self, mocked_run):
        good = "registry.example/repo@sha256:" + "1" * 64
        bad = "registry.example/other@sha256:" + "2" * 64
        class Result:
            returncode = 0
            stdout = __import__("json").dumps([bad, good])
            stderr = ""
        mocked_run.return_value = Result()
        self.assertEqual(audit.resolve_image_digest("registry.example/repo:tag"), good)

    @patch("ndv_run_s2_base_audit.run")
    def test_multiple_matching_digests_are_rejected(self, mocked_run):
        first = "registry.example/repo@sha256:" + "1" * 64
        second = "registry.example/repo@sha256:" + "2" * 64
        class Result:
            returncode = 0
            stdout = __import__("json").dumps([first, second])
            stderr = ""
        mocked_run.return_value = Result()
        with self.assertRaisesRegex(RuntimeError, "multiple RepoDigests"):
            audit.resolve_image_digest("registry.example/repo:tag")


if __name__ == "__main__":
    unittest.main()
