import copy
import unittest

from ndv_qualify_local_ollama_executor import candidate_is_valid, find_model, make_endpoint_record


PROBE = {
    "schema_id": "ndv-local-surface-probe-v1",
    "downloads_performed": False,
    "credentials_used": False,
    "ollama": {
        "cli": {"returncode": 0, "stdout": "ollama version 0.test"},
        "models": [
            {
                "name": "code-model:test",
                "digest": "sha256:" + "a" * 64,
                "quantization_level": "Q4_K_M",
                "parameter_size": "7B",
            }
        ],
    },
}


class LocalOllamaQualificationTests(unittest.TestCase):
    def test_exact_model_lookup(self):
        model = find_model(copy.deepcopy(PROBE), "code-model:test")
        self.assertEqual(model["name"], "code-model:test")

    def test_missing_model_fails_closed(self):
        with self.assertRaises(ValueError):
            find_model(copy.deepcopy(PROBE), "other")

    def test_candidate_oracle_accepts_exact_change(self):
        diff = "--- a/ndv_fixture.py\n+++ b/ndv_fixture.py\n@@\n-VALUE = 1\n+VALUE = 2\n"
        self.assertTrue(candidate_is_valid(diff))

    def test_candidate_oracle_rejects_prose(self):
        self.assertFalse(candidate_is_valid("I would change VALUE to 2."))

    def test_endpoint_record_does_not_authorize_wp04(self):
        model = find_model(copy.deepcopy(PROBE), "code-model:test")
        record = make_endpoint_record(
            copy.deepcopy(PROBE),
            model,
            "evidence.json",
            "b" * 64,
            "2026-09-16T14:00:00+00:00",
        )
        self.assertEqual(record["schema_id"], "ndv-wp05-local-model-endpoint-v1")
        self.assertEqual(record["classification"], "MODEL_ENDPOINT_QUALIFIED_NOT_EXECUTOR")
        self.assertFalse(record["repository_tool_access"])
        self.assertFalse(record["wp04_task_exposure_authorized"])


if __name__ == "__main__":
    unittest.main()
