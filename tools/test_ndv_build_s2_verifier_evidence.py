import unittest

from ndv_build_s2_verifier_evidence import build, sha256


class VerifierEvidenceBuilderTests(unittest.TestCase):
    def setUp(self):
        row = {"instance_id": "x-1", "repo": "org/repo", "base_commit": "a" * 40, "FAIL_TO_PASS": ["test_focal"], "PASS_TO_PASS": ["test_preserve"], "install_config": {"log_parser": "parse_log_pytest"}, "patch": "SECRET GOLD", "test_patch": "SECRET TEST PATCH"}
        self.admission = {"schema_id": "ndv-p1-s2-admission-only-row-v1", "candidate_id": "S2W01-x-1", "source": {"source_row_index": 7, "ndv_canonical_row_sha256": sha256(row)}, "full_row": row}
        self.parser = {"parser_name": "parse_log_pytest", "repository": "SWE-rebench/SWE-rebench-V2", "revision": "c" * 40, "path": "lib/agent/log_parsers.py", "blob_sha256": "d" * 64}

    def test_separates_focal_and_preservation_without_gold(self):
        result = build(self.admission, self.parser)
        self.assertEqual(result["focal"]["tests"], ["test_focal"])
        self.assertEqual(result["preservation"]["tests"], ["test_preserve"])
        self.assertEqual(result["focal"]["source_row_index"], 7)
        encoded = str(result)
        self.assertNotIn("SECRET GOLD", encoded)
        self.assertNotIn("SECRET TEST PATCH", encoded)

    def test_tampered_full_row_is_rejected(self):
        admission = dict(self.admission)
        admission["full_row"] = dict(self.admission["full_row"])
        admission["full_row"]["repo"] = "tampered/repo"
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            build(admission, self.parser)

    def test_parser_identity_must_match(self):
        parser = dict(self.parser); parser["parser_name"] = "parse_log_gotest"
        with self.assertRaisesRegex(ValueError, "parser provenance name mismatch"):
            build(self.admission, parser)

    def test_focal_must_be_nonempty(self):
        admission = {**self.admission, "full_row": dict(self.admission["full_row"])}
        admission["full_row"]["FAIL_TO_PASS"] = []
        admission["source"] = dict(self.admission["source"])
        admission["source"]["ndv_canonical_row_sha256"] = sha256(admission["full_row"])
        with self.assertRaisesRegex(ValueError, "FAIL_TO_PASS must be non-empty"):
            build(admission, self.parser)

    def test_duplicate_tests_rejected(self):
        admission = {**self.admission, "full_row": dict(self.admission["full_row"])}
        admission["full_row"]["PASS_TO_PASS"] = ["a", "a"]
        admission["source"] = dict(self.admission["source"])
        admission["source"]["ndv_canonical_row_sha256"] = sha256(admission["full_row"])
        with self.assertRaisesRegex(ValueError, "duplicates"):
            build(admission, self.parser)


if __name__ == "__main__":
    unittest.main()
