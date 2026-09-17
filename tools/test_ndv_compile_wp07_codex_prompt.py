import json
import tempfile
import unittest
from pathlib import Path

import ndv_compile_wp07_codex_prompt as mod


class CodexPromptCompilerTests(unittest.TestCase):
    def make_fixture(self, root: Path, shaping: str = "S0_RAW_TASK"):
        executor = {
            "schema_id":"ndv-p1-s2-executor-visible-row-v1",
            "candidate_id":"C1",
            "source_binding":{"dataset_revision":"rev","source_row_index":1,"ndv_canonical_row_sha256":"a"*64},
            "projection_policy":{"mode":"STRICT_ALLOWLIST"},
            "task_statement_sha256":"",
            "executor_visible_sha256":"",
            "task":{
                "instance_id":"inst-1",
                "repo":"org/repo",
                "base_commit":"b"*40,
                "problem_statement":"Fix the parser edge case.\n",
                "language":"Python"
            }
        }
        statement_sha = __import__("hashlib").sha256(executor["task"]["problem_statement"].encode()).hexdigest()
        executor["task_statement_sha256"] = statement_sha
        executor["executor_visible_sha256"] = mod.sha_value(executor["task"])
        ep = root/"executor-visible.json"
        ep.write_text(json.dumps(executor), encoding="utf-8")

        admission = {
            "schema_id":"ndv-p1-s2-admission-record-v2",
            "candidate_id":"C1",
            "source_instance_id":"inst-1",
            "source_row_index":1,
            "repository":"org/repo",
            "base_revision":"b"*40,
            "language":"Python",
            "family":"F1",
            "family_assignment":{"family":"F1","performance_based":False},
            "source_binding":{
                "task_statement_sha256":statement_sha,
                "ndv_canonical_row_sha256":"a"*64,
                "executor_visible_ref":str(ep),
                "executor_visible_sha256":executor["executor_visible_sha256"],
                "admission_only_ref":"unused.json",
                "quarantine_manifest_ref":"unused-q.json"
            },
            "audit":{},
            "artifact_integrity":{"status":"VERIFIED","executor_visible_file_sha256":mod.sha_file(ep)},
            "selection":{"treatment_performance_consulted":False,"treatment_execution_before_admission":False,"holdout_access":"NONE"},
            "status":"ADMITTED_FROZEN"
        }
        admission["record_sha256"] = mod.sha_value(admission)
        ap = root/"admission.json"
        ap.write_text(json.dumps(admission), encoding="utf-8")

        spec = {
            "schema_id":"ndv-p1-s2-run-spec-v1",
            "run_id":"R1",
            "phase":"P1-S2",
            "task":{
                "task_id":"C1",
                "base_sha":"b"*40,
                "task_statement_sha256":statement_sha,
                "admission_record_ref":str(ap),
                "admission_record_file_sha256":mod.sha_file(ap),
                "admission_record_sha256":admission["record_sha256"]
            },
            "treatment":{"id":"B0","shaping":shaping,"bindings":{}},
            "holdout":"DEVELOPMENT_ONLY",
            "execution_status":"NOT_EXECUTED"
        }
        sp = root/"run-spec.json"
        sp.write_text(json.dumps(spec), encoding="utf-8")
        return sp, ap, ep

    def test_s0_is_statement_only_with_one_terminal_newline(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp)
            sp, _, _ = self.make_fixture(r)
            out = mod.compile_prompt(sp, r)
            self.assertEqual(out["prompt"], "Fix the parser edge case.\n")
            self.assertFalse(out["forbidden_source_accessed"])
            self.assertFalse(out["task_prompt_exposed"])

    def test_s1_is_deterministic_wrapper(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp)
            sp, _, _ = self.make_fixture(r, "S1_DETERMINISTIC_TASK_SHAPING")
            out = mod.compile_prompt(sp, r)
            self.assertIn("Objective:\nFix the parser edge case.\n", out["prompt"])
            self.assertIn("repository: org/repo", out["prompt"])
            self.assertIn("base revision: " + "b"*40, out["prompt"])
            self.assertNotIn("secret", out["prompt"].lower())
            self.assertFalse(out["forbidden_source_accessed"])

    def test_executor_visible_byte_tamper_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp)
            sp, _, ep = self.make_fixture(r)
            ep.write_text(ep.read_text()+"\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "file SHA-256 mismatch"):
                mod.compile_prompt(sp, r)

    def test_unapproved_executor_field_blocks_even_if_hashes_recomputed(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp)
            sp, ap, ep = self.make_fixture(r)
            executor = json.loads(ep.read_text())
            executor["task"]["patch"] = "secret"
            executor["executor_visible_sha256"] = mod.sha_value(executor["task"])
            ep.write_text(json.dumps(executor), encoding="utf-8")
            admission = json.loads(ap.read_text())
            admission["source_binding"]["executor_visible_sha256"] = executor["executor_visible_sha256"]
            admission["artifact_integrity"]["executor_visible_file_sha256"] = mod.sha_file(ep)
            admission["record_sha256"] = mod.sha_value({k:v for k,v in admission.items() if k!="record_sha256"})
            ap.write_text(json.dumps(admission), encoding="utf-8")
            spec = json.loads(sp.read_text())
            spec["task"]["admission_record_file_sha256"] = mod.sha_file(ap)
            spec["task"]["admission_record_sha256"] = admission["record_sha256"]
            sp.write_text(json.dumps(spec), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unapproved fields"):
                mod.compile_prompt(sp, r)

    def test_admission_semantic_tamper_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp)
            sp, ap, _ = self.make_fixture(r)
            admission = json.loads(ap.read_text())
            admission["repository"] = "tampered/repo"
            ap.write_text(json.dumps(admission), encoding="utf-8")
            spec = json.loads(sp.read_text())
            spec["task"]["admission_record_file_sha256"] = mod.sha_file(ap)
            sp.write_text(json.dumps(spec), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "record_sha256 mismatch"):
                mod.compile_prompt(sp, r)


if __name__ == "__main__":
    unittest.main()
