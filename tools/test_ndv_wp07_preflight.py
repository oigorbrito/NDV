import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ndv_wp07_preflight as mod


class PreflightTests(unittest.TestCase):
    def args(self, root: Path):
        protocol=root/"protocol.json"; protocol.write_text(json.dumps({"schema_id":"ndv-p1-wp07-development-comparison-protocol-v1"}))
        bindings=root/"bindings.json"; bindings.write_text("{}")
        return argparse.Namespace(
            protocol=protocol, bindings=bindings, artifact_root=root,
            wp04_binding_import=root/"binding-import", wp04_closure=root/"closure.json",
            wp06_readiness=root/"readiness.json", wp07_release=root/"release.json",
            admission_record=[]
        )

    @mock.patch.object(mod.binding_readiness,"assess")
    def test_missing_empirical_artifacts_are_blockers_not_failures(self, binding_assess):
        binding_assess.return_value={
            "status":"BINDING_COVERAGE_INCOMPLETE","all_treatments_ready":False,
            "treatments":{"B0":{"ready":False,"missing_roles":["PRIMARY_STRONG"]}}
        }
        with tempfile.TemporaryDirectory() as tmp:
            result=mod.assess(self.args(Path(tmp)))
            self.assertEqual(result["status"],"BLOCKED_ON_EMPIRICAL_PREREQUISITES")
            self.assertTrue(result["blocked_is_not_failure"])
            self.assertTrue(result["blocked_cost_is_not_zero"])
            gates={b["gate"] for b in result["blockers"]}
            self.assertIn("WP04_BINDING_IMPORT",gates)
            self.assertIn("WP04_CLOSURE",gates)
            self.assertIn("WP06_READINESS",gates)
            self.assertIn("WP07_BINDING_COVERAGE",gates)
            self.assertIn("WP06_ADMISSION_RECORDS",gates)

    @mock.patch.object(mod.binding_readiness,"assess")
    @mock.patch.object(mod.matrix,"verify_admission")
    def test_all_prerequisites_can_reach_ready_state(self, verify_admission, binding_assess):
        binding_assess.return_value={"status":"ALL_TREATMENTS_BOUND","all_treatments_ready":True,"treatments":{}}
        verify_admission.return_value={"candidate_id":"C1"}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); args=self.args(root)
            imp=root/"binding-import"; imp.mkdir()
            (imp/"executor-binding-v2.json").write_text("{}")
            (imp/"qualification-evidence.json").write_text("{}")
            (imp/"binding-import-receipt.json").write_text(json.dumps({"schema_id":"ndv-wp04-binding-import-receipt-v2","status":"ORIGINAL_BINDING_AND_QUALIFICATION_PRESERVED"}))
            args.wp04_closure.write_text(json.dumps({"schema_id":"ndv-p1-wp04-campaign-closure-v1","status":"WP04_PIPELINE_SMOKE_COMPLETE"}))
            args.wp06_readiness.write_text(json.dumps({"schema_id":"ndv-p1-s2-corpus-readiness-assessment-v1","status":"WP06_INTAKE_TARGET_REACHED"}))
            args.wp07_release.write_text(json.dumps({"schema_id":"ndv-p1-wp07-development-comparison-release-v1","status":"WP07_DEVELOPMENT_COMPARISON_RELEASED"}))
            admission=root/"a.json"; admission.write_text("{}")
            args.admission_record=[admission]
            result=mod.assess(args)
            self.assertEqual(result["status"],"READY_TO_MATERIALIZE_RUN_MATRIX")
            self.assertEqual(result["blocker_count"],0)


if __name__=="__main__": unittest.main()
