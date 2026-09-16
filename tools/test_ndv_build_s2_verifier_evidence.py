import unittest

from ndv_build_s2_verifier_evidence import build


class VerifierEvidenceBuilderTests(unittest.TestCase):
    def setUp(self):
        self.admission = {
            "instance_id": "x-1",
            "repo": "org/repo",
            "base_commit": "a" * 40,
            "FAIL_TO_PASS": ["test_focal"],
            "PASS_TO_PASS": ["test_preserve"],
            "install_config": {"log_parser": "parse_log_pytest"},
            "patch": "SECRET GOLD",
            "test_patch": "SECRET TEST PATCH",
        }
        self.parser = {
            "parser_name": "parse_log_pytest",
            "repository": "SWE-rebench/SWE-rebench-V2",
            "revision": "c" * 40,
            "path": "lib/agent/log_parsers.py",
            "blob_sha": "d" * 40,
        }

    def test_separates_focal_and_preservation(self):
        result = build(self.admission, self.parser)
        self.assertEqual(result["focal"]["tests"], ["test_focal"])
        self.assertEqual(result["preservation"]["tests"], ["test_preserve"])
        encoded = str(result)
        self.assertNotIn("SECRET GOLD", encoded)
        self.assertNotIn("SECRET TEST PATCH", encoded)

    def test_parser_identity_must_match(self):
        parser = dict(self.parser)
        parser["parser_name"] = "parse_log_gotest"
        with self.assertRaisesRegex(ValueError, "parser provenance name mismatch"):
            build(self.admission, parser)

    def test_focal_must_be_nonempty(self):
        admission = dict(self.admission)
        admission["FAIL_TO_PASS"] = []
        with self.assertRaisesRegex(ValueError, "FAIL_TO_PASS must be non-empty"):
            build(admission, self.parser)

    def test_duplicate_tests_rejected(self):
        admission = dict(self.admission)
        admission["PASS_TO_PASS"] = ["a", "a"]
        with self.assertRaisesRegex(ValueError, "duplicates"):
            build(admission, self.parser)


if __name__ == "__main__":
    unittest.main()
