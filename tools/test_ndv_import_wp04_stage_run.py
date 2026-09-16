import unittest

from ndv_import_wp04_stage_run import parse_aider_tokens


class WP04ImportTests(unittest.TestCase):
    def test_parses_and_sums_aider_token_lines(self):
        result = parse_aider_tokens("Tokens: 8.3k sent, 81 received.\nTokens: 19k sent, 23 received.\n")
        self.assertEqual(result["input_tokens"], 27300)
        self.assertEqual(result["output_tokens"], 104)
        self.assertEqual(result["total_tokens"], 27404)
        self.assertTrue(result["approximate"])
        self.assertEqual(len(result["samples"]), 2)

    def test_missing_token_lines_stays_missing(self):
        result = parse_aider_tokens("no telemetry")
        self.assertIsNone(result["input_tokens"])
        self.assertIsNone(result["total_tokens"])


if __name__ == "__main__":
    unittest.main()
