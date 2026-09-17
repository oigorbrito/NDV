import unittest

import ndv_parse_codex_jsonl_usage as mod


class CodexUsageTests(unittest.TestCase):
    def test_sums_completed_turns(self):
        raw = "\n".join([
            '{"type":"thread.started","thread_id":"t1"}',
            '{"type":"turn.completed","usage":{"input_tokens":10,"cached_input_tokens":3,"cache_write_input_tokens":2,"output_tokens":4,"reasoning_output_tokens":1}}',
            '{"type":"turn.completed","usage":{"input_tokens":20,"cached_input_tokens":5,"cache_write_input_tokens":0,"output_tokens":6,"reasoning_output_tokens":2}}',
        ])
        r = mod.parse_lines(raw)
        self.assertEqual(r["status"], "AUTHORITATIVE")
        self.assertEqual(r["usage"]["input_tokens"], 30)
        self.assertEqual(r["usage"]["output_tokens"], 10)
        self.assertEqual(r["total_system_tokens_component"], 40)
        self.assertEqual(r["cached_input_tokens_recorded_separately"], 8)
        self.assertEqual(r["reasoning_output_tokens_recorded_separately"], 3)

    def test_no_completed_turn_is_missing_not_zero(self):
        r = mod.parse_lines('{"type":"thread.started","thread_id":"t1"}\n')
        self.assertEqual(r["status"], "MISSING")
        self.assertIsNone(r["usage"]["input_tokens"])
        self.assertIsNone(r["total_system_tokens_component"])
        self.assertFalse(r["missing_telemetry_is_zero"])

    def test_malformed_jsonl_blocks(self):
        with self.assertRaisesRegex(ValueError, "malformed JSONL"):
            mod.parse_lines('{"type":"turn.started"}\nnot-json\n')

    def test_missing_usage_field_blocks(self):
        with self.assertRaisesRegex(ValueError, "reasoning_output_tokens"):
            mod.parse_lines('{"type":"turn.completed","usage":{"input_tokens":1,"cached_input_tokens":0,"cache_write_input_tokens":0,"output_tokens":1}}')

    def test_negative_usage_blocks(self):
        with self.assertRaisesRegex(ValueError, "negative"):
            mod.parse_lines('{"type":"turn.completed","usage":{"input_tokens":-1,"cached_input_tokens":0,"cache_write_input_tokens":0,"output_tokens":1,"reasoning_output_tokens":0}}')

    def test_failure_events_are_recorded_without_inventing_usage(self):
        raw = '{"type":"turn.failed","error":{"message":"provider failed"}}\n{"type":"error","message":"fatal"}\n'
        r = mod.parse_lines(raw)
        self.assertEqual(r["status"], "MISSING")
        self.assertEqual(r["turn_failed_count"], 1)
        self.assertEqual(r["error_event_count"], 1)


if __name__ == "__main__":
    unittest.main()
