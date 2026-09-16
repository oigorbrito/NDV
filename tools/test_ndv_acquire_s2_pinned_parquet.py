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
            "schema_id": "ndv-p1-s2-source-snapshot-v1", "source_id": "SRC",
            "dataset": "org/data", "pinned_revision": "a" * 40, "parquet_path": "data/train.parquet",
            "parquet_remote_size_bytes": len(data), "parquet_sha256": hashlib.sha256(data).hexdigest(),
            "integrity_policy": {"admission_requires_strong_path": True}, "treatment_execution": "NOT_EXECUTED", "holdout_access": "NONE",
        }

    def contract(self):
        return {
            "schema_id": "ndv-p1-s2-parquet-acquisition-v1", "source_id": "SRC",
            "remote_url_template": "https://host/{dataset}/resolve/{revision}/{parquet_path}",
            "model_execution": "NONE", "treatment_execution": "NOT_EXECUTED", "holdout_access": "NONE",
        }

    def test_contract_binding_requires_same_source_id(self):
        contract = self.contract(); contract["source_id"] = "OTHER"
        with self.assertRaisesRegex(ValueError, "source_id mismatch"):
            mod.validate_contract_binding(self.snapshot(), contract)

    def test_contaminated_snapshot_rejected(self):
        snapshot = self.snapshot(); snapshot["holdout_access"] = "YES"
        with self.assertRaisesRegex(ValueError, "contaminated"):
            mod.validate_contract_binding(snapshot, self.contract())

    def test_url_is_bound_to_exact_revision_and_path(self):
        self.assertEqual(mod.build_url(self.snapshot(), self.contract()), "https://host/org/data/resolve/" + "a" * 40 + "/data/train.parquet")

    def test_unsafe_path_rejected(self):
        snapshot = self.snapshot(); snapshot["parquet_path"] = "../secret"
        with self.assertRaises(ValueError): mod.build_url(snapshot, self.contract())

    def test_verify_file_checks_size_and_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x"; path.write_bytes(b"fixture"); snap = self.snapshot()
            result = mod.verify_file(path, snap["parquet_remote_size_bytes"], snap["parquet_sha256"])
            self.assertTrue(result["size_match"]); self.assertTrue(result["sha256_match"])

    @mock.patch("ndv_acquire_s2_pinned_parquet.urllib.request.urlopen")
    def test_download_streams_to_partial(self, urlopen):
        cm = mock.MagicMock(); cm.__enter__.return_value = io.BytesIO(b"abcdef"); cm.__exit__.return_value = False; urlopen.return_value = cm
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.part"; written = mod.download("https://example.invalid/x", path, chunk_size=2)
            self.assertEqual(written, 6); self.assertEqual(path.read_bytes(), b"abcdef")

    def test_existing_mismatch_can_be_detected_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); snapshot = root / "snapshot.json"; snapshot.write_text(json.dumps(self.snapshot()), encoding="utf-8"); contract = root / "contract.json"; contract.write_text(json.dumps(self.contract()), encoding="utf-8"); out = root / "data.parquet"; out.write_bytes(b"wrong")
            argv = ["prog", "--snapshot", str(snapshot), "--contract", str(contract), "--out", str(out)]
            with mock.patch("sys.argv", argv):
                with self.assertRaisesRegex(SystemExit, "refusing overwrite"): mod.main()

    def test_verified_existing_file_writes_byte_bound_receipt_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); data = b"fixture"; snapshot = root / "snapshot.json"; snapshot.write_text(json.dumps(self.snapshot(data)), encoding="utf-8"); contract = root / "contract.json"; contract.write_text(json.dumps(self.contract()), encoding="utf-8"); out = root / "data.parquet"; out.write_bytes(data); receipt = root / "receipt.json"
            argv = ["prog", "--snapshot", str(snapshot), "--contract", str(contract), "--out", str(out), "--receipt", str(receipt)]
            with mock.patch("sys.argv", argv), mock.patch("builtins.print"):
                self.assertEqual(mod.main(), 0)
            payload = json.loads(receipt.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_id"], "ndv-p1-s2-parquet-acquisition-receipt-v2")
            self.assertEqual(payload["status"], "REUSED_VERIFIED_EXISTING")
            self.assertFalse(payload["network_used"])
            self.assertEqual(payload["source_snapshot_file_sha256"], mod.sha256_file(snapshot))
            self.assertEqual(payload["acquisition_contract_file_sha256"], mod.sha256_file(contract))


if __name__ == "__main__": unittest.main()
