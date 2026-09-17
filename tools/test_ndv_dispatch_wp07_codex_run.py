import json, tempfile, unittest
from pathlib import Path
from unittest import mock

import ndv_dispatch_wp07_codex_run as mod


class CodexDispatcherTests(unittest.TestCase):
    def fixture(self, root: Path, treatment="B1"):
        release=root/"release.json"
        release.write_text(json.dumps({
            "schema_id":"ndv-p1-wp07-development-comparison-release-v1",
            "status":"WP07_DEVELOPMENT_COMPARISON_RELEASED","holdout_access":"NONE",
            "authorized_scope":{"development_corpus_comparative_treatment_execution":True,"sealed_holdout_access":False,"claim_generation":False,"architecture_decision":False},
            "execution_constraints":{"preserve_preregistered_treatments":True,"preserve_zero_unplanned_fallback":True,"verified_result_required":True}
        }))
        spec={"schema_id":"ndv-p1-s2-run-spec-v1","run_id":"R1","execution_status":"NOT_EXECUTED","holdout":"DEVELOPMENT_ONLY","task":{"task_id":"T1"},"treatment":{"id":treatment}}
        matrix=root/"matrix.json"
        matrix.write_text(json.dumps({"schema_id":"ndv-p1-wp07-run-matrix-v1","status":"RUN_SPECS_MATERIALIZED_NOT_EXECUTED","release_ref":str(release),"release_file_sha256":mod.sha_file(release),"run_specs":[spec],"treatment_execution":"NOT_EXECUTED","holdout_access":"NONE"}))
        return matrix,release

    def test_wrong_token_blocks_before_matrix_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(mod,"select_released_spec") as select:
                with self.assertRaisesRegex(ValueError,"execution token"):
                    mod.dispatch(Path(tmp)/"missing.json","R1",Path(tmp),Path(tmp),Path(tmp)/"out","WRONG",mod.VERIFY_TOKEN)
                select.assert_not_called()

    def test_release_hash_tamper_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);matrix,release=self.fixture(root);release.write_text("{}")
            with self.assertRaisesRegex(ValueError,"release file hash mismatch"):
                mod.select_released_spec(matrix,root,"R1")

    def test_duplicate_run_id_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);matrix,_=self.fixture(root);payload=json.loads(matrix.read_text());payload["run_specs"].append(dict(payload["run_specs"][0]));matrix.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError,"resolve exactly once"):
                mod.select_released_spec(matrix,root,"R1")

    @mock.patch.object(mod,"verify")
    @mock.patch.object(mod,"execute")
    @mock.patch.object(mod,"materialize")
    def test_b1_uses_single_hop_only(self, materialize, execute, verify):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);matrix,_=self.fixture(root,"B1")
            def mat(_spec,_root,out):out.mkdir(parents=True);(out/"workspace-manifest.json").write_text("{}")
            materialize.side_effect=mat
            def exe(_spec,_manifest,_root,out,_token):out.mkdir(parents=True);(out/"executor-stage-report.json").write_text("{}") ;return {"classification":{"pending_verification":True}}
            execute.side_effect=exe
            def ver(_report,_root,_upstream,out,_token):out.mkdir(parents=True);p=out/"verification-report.json";p.write_text("{}") ;return {"verified_solved_task":"YES","failure_attribution":None}
            verify.side_effect=ver
            with mock.patch.object(mod,"cascade") as cascade:
                r=mod.dispatch(matrix,"R1",root,root,root/"out",mod.EXECUTE_TOKEN,mod.VERIFY_TOKEN)
                self.assertEqual(r["dispatch_route"],"STATIC_SINGLE_HOP");self.assertEqual(r["verified_solved_task"],"YES")
                materialize.assert_called_once();execute.assert_called_once();verify.assert_called_once();cascade.assert_not_called()

    @mock.patch.object(mod,"cascade")
    def test_b2_uses_only_frozen_cascade(self,cascade):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);matrix,_=self.fixture(root,"B2");b2=root/"b2-contract.json";b2.write_text("{}")
            def cas(_spec,_root,_upstream,out,_contract,_exec,_verify):out.mkdir(parents=True);(out/"cascade-report.json").write_text("{}") ;return {"verified_solved_task":"NO","failure_attribution":"PRODUCT_FAILURE"}
            cascade.side_effect=cas
            with mock.patch.object(mod,"materialize") as materialize, mock.patch.object(mod,"execute") as execute:
                r=mod.dispatch(matrix,"R1",root,root,root/"out",mod.EXECUTE_TOKEN,mod.VERIFY_TOKEN,b2)
                self.assertEqual(r["dispatch_route"],"B2_FROZEN_CASCADE");self.assertEqual(r["verified_solved_task"],"NO")
                cascade.assert_called_once();materialize.assert_not_called();execute.assert_not_called()

    @mock.patch.object(mod,"cascade")
    @mock.patch.object(mod,"execute")
    @mock.patch.object(mod,"materialize")
    def test_b4_fails_closed_without_any_codex_execution(self,materialize,execute,cascade):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);matrix,_=self.fixture(root,"B4")
            with self.assertRaisesRegex(ValueError,"local-first controller required"):
                mod.dispatch(matrix,"R1",root,root,root/"out",mod.EXECUTE_TOKEN,mod.VERIFY_TOKEN)
            materialize.assert_not_called();execute.assert_not_called();cascade.assert_not_called()

    @mock.patch.object(mod,"execute")
    @mock.patch.object(mod,"materialize")
    def test_selected_path_failure_has_no_fallback(self,materialize,execute):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);matrix,_=self.fixture(root,"B0")
            def mat(_spec,_root,out):out.mkdir(parents=True);(out/"workspace-manifest.json").write_text("{}")
            materialize.side_effect=mat;execute.side_effect=ValueError("selected executor failed")
            with mock.patch.object(mod,"cascade") as cascade:
                with self.assertRaisesRegex(ValueError,"selected executor failed"):
                    mod.dispatch(matrix,"R1",root,root,root/"out",mod.EXECUTE_TOKEN,mod.VERIFY_TOKEN)
                cascade.assert_not_called();self.assertEqual(execute.call_count,1)

    def test_holdout_spec_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);matrix,_=self.fixture(root,"B3");payload=json.loads(matrix.read_text());payload["run_specs"][0]["holdout"]="SEALED";matrix.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError,"development-only"):
                mod.select_released_spec(matrix,root,"R1")


if __name__=="__main__":unittest.main()
