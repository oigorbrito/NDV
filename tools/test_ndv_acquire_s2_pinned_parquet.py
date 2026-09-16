import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ndv_acquire_s2_pinned_parquet as mod


class AcquisitionTests(unittest.TestCase):
    def snapshot(self, data: bytes = b"fixture"):
        return {
            "dataset": "org/data",
            "pinned_revision": "a" * 40,
            "parquet_path": "data/train.parquet",
            "parquet_remote_size_bytes": len(data),
            "parquet_sha256": hashlib.sha256(data).hexdigest(),
        }

    def contract(self):
        return {"schema_id": "ndv-p1-s2-parquet-acquisition-v1", "remote_url_template": "https://host/{dataset}/resolve/{revision}/{parquet_path}"}

    def test_url_is_bound_to_exact_revision_and_path(self):
        url = mod.build_url(self.snapshot(), self.contract())
        self.assertEqual(url, "https://host/org/data/resolve/" + "a" * 40 + "/data/train.parquet")

    def test_unsafe_path_rejected(self):
        snapshot = self.snapshot(); snapshot["parquet_path"] = "../secret"
        with self.assertRaises(ValueError):
            mod.build_url(snapshot, self.contract())

    def test_verify_file_checks_size_and_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x"
            path.write_bytes(b"fixture")
            snap = self.snapshot()
            result = mod.verify_file(path, snap["parquet_remote_size_bytes"], snap["parquet_sha256"])
            self.assertTrue(result["size_match"])
            self.assertTrue(result["sha256_match"])

    @mock.patch("ndv_acquire_s2_pinned_parquet.urllib.request.urlopen")
    def test_download_streams_to_partial(self, urlopen):
        response = io.BytesIO(b"abcdef")
        response.__enter__ = lambda self: self
        response.__exit__ = lambda *args: None
        urlopen.return_value = response
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.part"
            written = mod.download("https://example.invalid/x", path, chunk_size=2)
            self.assertEqual(written, 6)
            self.assertEqual(path.read_bytes(), b"abcdef")

    def test_existing_mismatch_can_be_detected_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot = root / "snapshot.json"; snapshot.write_text(json.dumps(self.snapshot()), encoding="utf-8")
            contract = root / "contract.json"; contract.write_text(json.dumps(self.contract()), encoding="utf-8")
            out = root / "data.parquet"; out.write_bytes(b"wrong")
            argv = ["prog", "--snapshot", str(snapshot), "--contract", str(contract), "--out", str(out)]
            with mock.patch("sys.argv", argv):
                with self.assertRaisesRegex(SystemExit, "refusing overwrite"):
                    mod.main()


if __name__ == "__main__":
    unittest.main()
