import json
import tempfile
import unittest
from pathlib import Path

import ndv_import_wp04_binding as mod


class BindingImportTests(unittest.TestCase):
    def binding(self):
        return {
            "schema_id": "ndv-p1-wp04-executor-binding-v2",
            "binding_id": "B1",
            "surface_class": "LOCAL_PINNED",
            "executor_kind": "MODEL_PLUS_FROZEN_SCAFFOLD",
            "provider_or_runtime": "Ollama local runtime + Aider",
            "exact_executor_identity": "aider(aider 0.86.2)+qwen2.5-coder:3b",
            "version_or_model_hash": "aider:aider 0.86.2|ollama:" + "a" * 64,
            "invocation_command_or_surface": "aider --model ollama_chat/qwen2.5-coder:3b --message <RAW_TASK>",
            "qualification_evidence_ref": "qualification.json",
            "qualification_evidence_sha256": "b" * 64,
            "candidate_capture_mode": "ISOLATED_WORKTREE_GIT_DIFF",
            "network_policy": "LOCAL_OLLAMA_REQUIRED",
            "frozen_at": "2026-09-16T00:00:00Z",
            "status": "QUALIFIED",
            "scaffold": {
                "name": "aider", "source_repository": "Aider-AI/aider", "version_or_commit": "aider 0.86.2",
                "invocation_mode": "noninteractive --message repository edit", "repository_tool_access": True,
                "implicit_model_fallback": False, "dynamic_routing": False, "executable_path": "C:/x/aider.exe",
            },
            "model": {"identity": "qwen2.5-coder:3b", "digest_or_exact_version": "a" * 64, "endpoint": "http://127.0.0.1:11434"},
            "timeout_seconds": 300, "retry_limit": 0, "escalation_limit": 0,
            "automatic_download": False, "implicit_fallback": False, "dynamic_routing": False,
            "task_context_mode": "RAW_TASK_PLUS_REPOSITORY_TOOL_ACCESS",
            "telemetry_mode": {"identity": "x", "usage": "x", "timestamps": "x", "raw_response_or_local_trace": "x"},
        }

    def report(self):
        return {
            "schema_id": "ndv-wp04-stage1-run-v1", "task_id": "D-F5-01", "binding_id": "B1",
            "executor_identity": "aider(aider 0.86.2)+qwen2.5-coder:3b",
            "retry_count": 0, "escalation_count": 0, "holdout_access": "NONE",
        }

    def test_original_binding_matches_stage1(self):
        mod.validate_original(self.binding(), self.report())

    def test_wrong_binding_id_rejected(self):
        b = self.binding(); b["binding_id"] = "OTHER"
        with self.assertRaisesRegex(ValueError, "binding_id"):
            mod.validate_original(b, self.report())

    def test_wrong_executor_identity_rejected(self):
        b = self.binding(); b["exact_executor_identity"] = "other"
        with self.assertRaisesRegex(ValueError, "executor identity"):
            mod.validate_original(b, self.report())

    def test_dynamic_behavior_rejected_by_contract(self):
        b = self.binding(); b["dynamic_routing"] = True
        with self.assertRaisesRegex(ValueError, "contract invalid"):
            mod.validate_original(b, self.report())


if __name__ == "__main__": unittest.main()
