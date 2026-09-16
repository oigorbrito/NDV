import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ndv_extract_pinned_swe_rebench_rows as mod


class PinnedExtractionTests(unittest.TestCase):
    def test_sha256_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.bin"
            p.write_bytes(b"abc")
            self.assertEqual(
                mod.sha256_file(p),
                hashlib.sha256(b"abc").hexdigest(),
            )

    def test_extract_rows_requires_indices(self):
        with self.assertRaises(SystemExit):
            mod.extract_rows(Path("unused.parquet"), [])

    @mock.patch.object(mod, "extract_rows")
    @mock.patch.object(mod, "sha256_file")
    def test_identity_binding_rejects_wrong_instance(self, sha_mock, extract_mock):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parquet = root / "data.parquet"
            parquet.write_bytes(b"fixture")
            snapshot = root / "snapshot.json"
            snapshot.write_text(json.dumps({
                "parquet_sha256": "a" * 64,
                "pinned_revision": "b" * 40,
            }), encoding="utf-8")
            wave = root / "wave.json"
            wave.write_text(json.dumps({
                "source": {"dataset_revision": "b" * 40},
                "candidates": [{
                    "source_row_index": 0,
                    "source_instance_id": "expected",
                    "base_revision": "c" * 40,
                }],
            }), encoding="utf-8")
            sha_mock.return_value = "a" * 64
            extract_mock.return_value = [{
                "instance_id": "wrong",
                "base_commit": "c" * 40,
            }]

            argv = [
                "prog",
                "--parquet", str(parquet),
                "--snapshot", str(snapshot),
                "--wave", str(wave),
                "--out", str(root / "rows.jsonl"),
            ]
            with mock.patch("sys.argv", argv), mock.patch("builtins.print"):
                self.assertEqual(mod.main(), 2)

    @mock.patch.object(mod, "extract_rows")
    @mock.patch.object(mod, "sha256_file")
    def test_happy_path_writes_selected_rows(self, sha_mock, extract_mock):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parquet = root / "data.parquet"
            parquet.write_bytes(b"fixture")
            snapshot = root / "snapshot.json"
            snapshot.write_text(json.dumps({
                "parquet_sha256": "a" * 64,
                "pinned_revision": "b" * 40,
            }), encoding="utf-8")
            wave = root / "wave.json"
            wave.write_text(json.dumps({
                "source": {"dataset_revision": "b" * 40},
                "candidates": [{
                    "source_row_index": 7,
                    "source_instance_id": "inst",
                    "base_revision": "c" * 40,
                }],
            }), encoding="utf-8")
            sha_mock.return_value = "a" * 64
            extract_mock.return_value = [{
                "instance_id": "inst",
                "base_commit": "c" * 40,
                "problem_statement": "fix me",
            }]
            out = root / "rows.jsonl"
            argv = [
                "prog",
                "--parquet", str(parquet),
                "--snapshot", str(snapshot),
                "--wave", str(wave),
                "--out", str(out),
            ]
            with mock.patch("sys.argv", argv), mock.patch("builtins.print"):
                self.assertEqual(mod.main(), 0)
            self.assertTrue(out.exists())
            row = json.loads(out.read_text(encoding="utf-8").strip())
            self.assertEqual(row["instance_id"], "inst")


if __name__ == "__main__":
    unittest.main()
