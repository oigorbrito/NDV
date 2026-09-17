import json
import tempfile
import unittest
from pathlib import Path

import ndv_release_wp07_development_comparison as mod


class WP07ReleaseTests(unittest.TestCase):
    def write_inputs(self, root: Path, *, ready=True):
        wp04 = root / "wp04.json"
        wp04.write_text(json.dumps({
            "schema_id": "ndv-p1-wp04-campaign-closure-v1", "status": "WP04_PIPELINE_SMOKE_COMPLETE",
            "integrity": {"raw_evidence_preserved": True, "treatment_reexecuted": False, "retries": 0, "escalations": 0, "holdout_access": "NONE"},
            "authority": {"pipeline_smoke": "COMPLETE", "comparative_p1_release": "NO"},
        }))
        intake = root / "intake.json"; intake.write_text(json.dumps({"schema_id":"ndv-p1-s2-corpus-intake-v1"}))
        legacy = root / "legacy.json"; legacy.write_text(json.dumps({"schema_id":"ndv-dv-legacy-manifest-v1"}))
        records=[]; ids=[]
        for i in range(5):
            payload={"schema_id":"ndv-p1-s2-admission-record-v2","status":"ADMITTED_FROZEN","candidate_id":f"C{i}"}
            payload["record_sha256"]=mod.sha({k:v for k,v in payload.items() if k!="record_sha256"})
            p=root/f"r{i}.json"; p.write_text(json.dumps(payload)); ids.append(payload["candidate_id"])
            records.append({"ref":str(p.resolve()),"file_sha256":mod.sha_file(p),"record_sha256":payload["record_sha256"]})
        readiness = root / "readiness.json"
        readiness.write_text(json.dumps({
            "schema_id": "ndv-p1-s2-corpus-readiness-assessment-v1",
            "status": "WP06_INTAKE_TARGET_REACHED" if ready else "WP06_INTAKE_TARGET_NOT_REACHED",
            "inputs": {"intake_ref":str(intake.resolve()),"intake_file_sha256":mod.sha_file(intake),"legacy_manifest_ref":str(legacy.resolve()),"legacy_manifest_file_sha256":mod.sha_file(legacy)},
            "checks": {"a": ready, "b": ready}, "combined_task_count": 9,
            "s2": {"admitted_count":5,"candidate_ids":ids,"records":records},
            "comparative_corpus_ready": "NO", "wp07_release": "NO",
            "treatment_execution": "NOT_EXECUTED", "holdout_access": "NONE",
        }))
        return wp04, readiness

    def test_valid_prerequisites_release_development_comparison_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            wp04, readiness = self.write_inputs(Path(tmp)); result = mod.release(wp04, readiness)
            self.assertEqual(result["status"], "WP07_DEVELOPMENT_COMPARISON_RELEASED")
            self.assertTrue(result["authorized_scope"]["development_corpus_comparative_treatment_execution"])
            self.assertFalse(result["authorized_scope"]["sealed_holdout_access"])
            self.assertFalse(result["authorized_scope"]["claim_generation"])
            self.assertTrue(result["prerequisites"]["wp06_source_chain_revalidated"])

    def test_wp06_not_ready_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            wp04, readiness = self.write_inputs(Path(tmp), ready=False)
            with self.assertRaisesRegex(ValueError, "intake target"): mod.release(wp04, readiness)

    def test_wp04_integrity_drift_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); wp04,readiness=self.write_inputs(root); payload=json.loads(wp04.read_text()); payload["integrity"]["retries"]=1; wp04.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError,"integrity"): mod.release(wp04,readiness)

    def test_wp06_self_authorization_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); wp04,readiness=self.write_inputs(root); payload=json.loads(readiness.read_text()); payload["wp07_release"]="YES"; readiness.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError,"self-authorize"): mod.release(wp04,readiness)

    def test_holdout_contamination_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); wp04,readiness=self.write_inputs(root); payload=json.loads(readiness.read_text()); payload["holdout_access"]="ACCESSED"; readiness.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError,"contamination"): mod.release(wp04,readiness)

    def test_tampered_admission_record_blocks_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); wp04,readiness=self.write_inputs(root); payload=json.loads(readiness.read_text()); p=Path(payload["s2"]["records"][0]["ref"]); r=json.loads(p.read_text()); r["candidate_id"]="TAMPERED"; p.write_text(json.dumps(r))
            with self.assertRaisesRegex(ValueError,"admission record hash mismatch"): mod.release(wp04,readiness)

    def test_tampered_intake_contract_blocks_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); wp04,readiness=self.write_inputs(root); payload=json.loads(readiness.read_text()); p=Path(payload["inputs"]["intake_ref"]); p.write_text("{}")
            with self.assertRaisesRegex(ValueError,"intake contract hash mismatch"): mod.release(wp04,readiness)


if __name__ == "__main__": unittest.main()
