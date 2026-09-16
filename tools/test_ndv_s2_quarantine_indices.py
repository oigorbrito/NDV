import json
import tempfile
import unittest
from pathlib import Path

from ndv_extract_pinned_swe_rebench_rows import make_record
from ndv_quarantine_swe_rebench_rows import load_records, find_row


class S2QuarantineIndexTests(unittest.TestCase):
    def test_selected_row_envelopes_preserve_original_indices(self):
        values = [
            make_record(2, {"instance_id": "a", "repo": "x/y", "base_commit": "a" * 40, "problem_statement": "one"}),
            make_record(12, {"instance_id": "b", "repo": "x/z", "base_commit": "b" * 40, "problem_statement": "two"}),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.jsonl"
            path.write_text("\n".join(json.dumps(v) for v in values) + "\n", encoding="utf-8")
            records = load_records(path)
        self.assertEqual([idx for idx, _ in records], [2, 12])
        idx, row = find_row(records, {"source_instance_id": "b", "source_row_index": 12})
        self.assertEqual(idx, 12)
        self.assertEqual(row["instance_id"], "b")

    def test_compacted_index_mismatch_fails_closed(self):
        records = [(0, {"instance_id": "b"})]
        with self.assertRaises(ValueError):
            find_row(records, {"source_instance_id": "b", "source_row_index": 12})

    def test_duplicate_envelope_indices_rejected(self):
        values = [make_record(2, {"instance_id": "a"}), make_record(2, {"instance_id": "b"})]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.jsonl"
            path.write_text("\n".join(json.dumps(v) for v in values) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_records(path)


if __name__ == "__main__":
    unittest.main()
