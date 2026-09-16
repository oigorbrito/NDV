import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ndv_materialize_s2_wave as mod


class MaterializationTests(unittest.TestCase):
    def fixture(self, root: Path, data: bytes = b"parquet-bytes"):
        parquet = root / "data.parquet"; parquet.write_bytes(data)
        snapshot = root / "snapshot.json"
        snapshot_payload = {
            "schema_id": "ndv-p1-s2-source-snapshot-v1", "source_id": "SRC-X", "dataset": "org/data",
            "pinned_revision": "a" * 40, "parquet_path": "data/train.parquet",
            "parquet_remote_size_bytes": len(data), "parquet_sha256": hashlib.sha256(data).hexdigest(),
            "treatment_execution": "NOT_EXECUTED", "holdout_access": "NONE",
        }
        snapshot.write_text(json.dumps(snapshot_payload), encoding="utf-8")
        contract = root / "contract.json"
        contract_payload = {"schema_id": "ndv-p1-s2-parquet-acquisition-v1", "source_id": "SRC-X"}
        contract.write_text(json.dumps(contract_payload), encoding="utf-8")
        receipt = root / "acquisition.json"
        receipt_payload = {
            "schema_id": "ndv-p1-s2-parquet-acquisition-receipt-v2", "status": "DOWNLOADED_VERIFIED", "source_id": "SRC-X",
            "source_snapshot_file_sha256": mod.sha256_file(snapshot), "acquisition_contract_file_sha256": mod.sha256_file(contract),
            "dataset": "org/data", "pinned_revision": "a" * 40, "parquet_path": "data/train.parquet",
            "expected_size_bytes": len(data), "expected_sha256": hashlib.sha256(data).hexdigest(),
            "observed": {"size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "size_match": True, "sha256_match": True},
            "treatment_execution": "NOT_EXECUTED", "holdout_access": "NONE",
        }
        receipt.write_text(json.dumps(receipt_payload), encoding="utf-8")
        return parquet, receipt, snapshot, contract

    def test_verified_acquisition_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.fixture(Path(tmp))
            result = mod.verify_acquisition(*paths)
            self.assertEqual(result["parquet_sha256"], hashlib.sha256(b"parquet-bytes").hexdigest())
            self.assertEqual(result["parquet_size_bytes"], len(b"parquet-bytes"))

    def test_tampered_parquet_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            parquet, receipt, snapshot, contract = self.fixture(Path(tmp))
            parquet.write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "Parquet bytes"):
                mod.verify_acquisition(parquet, receipt, snapshot, contract)

    def test_tampered_snapshot_is_rejected_by_receipt_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            parquet, receipt, snapshot, contract = self.fixture(Path(tmp))
            payload = json.loads(snapshot.read_text()); payload["dataset"] = "other/data"; snapshot.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "snapshot file SHA-256"):
                mod.verify_acquisition(parquet, receipt, snapshot, contract)

    def test_receipt_contamination_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            parquet, receipt, snapshot, contract = self.fixture(Path(tmp))
            payload = json.loads(receipt.read_text()); payload["treatment_execution"] = "EXECUTED"; receipt.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "contamination"):
                mod.verify_acquisition(parquet, receipt, snapshot, contract)

    @mock.patch.object(mod, "run_extraction")
    @mock.patch.object(mod, "verify_acquisition")
    def test_main_writes_materialization_receipt_after_full_quarantine(self, verify, run_extraction):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); parquet = root / "data.parquet"; parquet.write_bytes(b"x")
            acquisition = root / "acq.json"; acquisition.write_text("{}")
            snapshot = root / "snapshot.json"; snapshot.write_text("{}")
            contract = root / "contract.json"; contract.write_text("{}")
            wave = root / "wave.json"; wave.write_text(json.dumps({"wave_id": "w1", "candidates": [{}, {}]}))
            extractor = root / "extractor.py"; extractor.write_text("# fixture")
            out_root = root / "out"
            verify.return_value = {"parquet_sha256": "a" * 64, "parquet_size_bytes": 1, "receipt_file_sha256": "b" * 64, "snapshot_file_sha256": "c" * 64, "contract_file_sha256": "d" * 64}
            class P: returncode = 0; stdout = ""; stderr = ""
            run_extraction.return_value = P()
            def side_effect(*_args, **_kwargs):
                rows = out_root / "pinned-rows.jsonl"; rows.parent.mkdir(parents=True, exist_ok=True); rows.write_text("{}\n")
                q = out_root / "quarantine" / "quarantine-aggregate.json"; q.parent.mkdir(parents=True, exist_ok=True); q.write_text(json.dumps({"schema_id": "ndv-p1-s2-quarantine-aggregate-v2", "wave_id": "w1", "candidate_count": 2, "passed_count": 2}))
                return P()
            run_extraction.side_effect = side_effect
            argv = ["prog", "--parquet", str(parquet), "--acquisition-receipt", str(acquisition), "--snapshot", str(snapshot), "--contract", str(contract), "--wave", str(wave), "--extractor", str(extractor), "--out-root", str(out_root)]
            with mock.patch("sys.argv", argv), mock.patch("builtins.print"):
                self.assertEqual(mod.main(), 0)
            receipt_payload = json.loads((out_root / "materialization-receipt.json").read_text())
            self.assertEqual(receipt_payload["status"], "MATERIALIZED_QUARANTINED")
            self.assertEqual(receipt_payload["passed_count"], 2)
            self.assertEqual(receipt_payload["treatment_execution"], "NOT_EXECUTED")
            self.assertFalse(receipt_payload["network_used"])


if __name__ == "__main__": unittest.main()
