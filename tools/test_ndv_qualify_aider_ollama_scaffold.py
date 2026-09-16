import copy
import unittest

from ndv_qualify_aider_ollama_scaffold import diff_is_valid, find_model, make_binding, parse_aider_version


PROBE = {
    "ollama": {
        "models": [
            {
                "name": "qwen2.5-coder:3b",
                "digest": "f" * 64,
                "quantization_level": "Q4_K_M",
            }
        ]
    }
}


class AiderScaffoldQualificationTests(unittest.TestCase):
    def test_exact_model_lookup(self):
        model = find_model(copy.deepcopy(PROBE), "qwen2.5-coder:3b")
        self.assertEqual(model["digest"], "f" * 64)

    def test_missing_model_fails_closed(self):
        with self.assertRaises(ValueError):
            find_model(copy.deepcopy(PROBE), "other")

    def test_diff_oracle(self):
        self.assertTrue(diff_is_valid("diff --git a/fixture.py b/fixture.py\n-VALUE = 1\n+VALUE = 2\n"))
        self.assertFalse(diff_is_valid("VALUE = 2\n"))

    def test_parse_version(self):
        self.assertEqual(parse_aider_version("aider 0.test\n"), "aider 0.test")

    def test_binding_v2_has_scaffold_and_model(self):
        binding = make_binding(
            aider_version="aider 0.test",
            model_name="qwen2.5-coder:3b",
            model_digest="f" * 64,
            evidence_ref="evidence.json",
            evidence_sha="a" * 64,
            frozen_at="2026-09-16T15:00:00+00:00",
            timeout_seconds=300,
        )
        self.assertEqual(binding["schema_id"], "ndv-p1-wp04-executor-binding-v2")
        self.assertEqual(binding["executor_kind"], "MODEL_PLUS_FROZEN_SCAFFOLD")
        self.assertTrue(binding["scaffold"]["repository_tool_access"])
        self.assertFalse(binding["scaffold"]["dynamic_routing"])
        self.assertEqual(binding["model"]["identity"], "qwen2.5-coder:3b")
        self.assertEqual(binding["retry_limit"], 0)
        self.assertEqual(binding["escalation_limit"], 0)


if __name__ == "__main__":
    unittest.main()
