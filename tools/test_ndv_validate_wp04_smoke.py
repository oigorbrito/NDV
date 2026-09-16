import copy
import unittest

from ndv_validate_wp04_smoke import validate_binding, validate_campaign


CAMPAIGN = {
    "schema_id": "ndv-p1-wp04-real-executor-smoke-v1",
    "scope": {
        "classification": "PIPELINE_SMOKE_ONLY",
        "executor_ranking": "FORBIDDEN",
        "economic_superiority_claim": "FORBIDDEN",
        "routing_claim": "FORBIDDEN",
        "architecture_claim": "FORBIDDEN",
        "holdout_access": "FORBIDDEN",
        "retries": 0,
        "escalations": 0,
        "shaping": "S0_RAW_TASK",
    },
    "executor_binding_policy": {
        "provider_neutral": True,
        "dynamic_or_random_routing": "FORBIDDEN",
        "automatic_download": "FORBIDDEN",
        "implicit_fallback": "FORBIDDEN",
    },
    "task_sequence": [
        {"stage": 1, "task_id": "D-F5-01"},
        {"stage": 2, "task_id": "D-F6-01"},
    ],
}

BINDING = {
    "schema_id": "ndv-p1-wp04-executor-binding-v2",
    "binding_id": "x2",
    "surface_class": "LOCAL_PINNED",
    "executor_kind": "MODEL_PLUS_FROZEN_SCAFFOLD",
    "provider_or_runtime": "Ollama local runtime",
    "exact_executor_identity": "aider+qwen2.5-coder:3b",
    "version_or_model_hash": "scaffold-commit+model-digest",
    "scaffold": {
        "name": "aider",
        "source_repository": "Aider-AI/aider",
        "version_or_commit": "5dc9490bb35f9729ef2c95d00a19ccd30c26339c",
        "invocation_mode": "terminal coding agent",
        "repository_tool_access": True,
        "implicit_model_fallback": False,
        "dynamic_routing": False,
    },
    "model": {
        "identity": "qwen2.5-coder:3b",
        "digest_or_exact_version": "f72c60cabf6237b07f6e632b2c48d533cef25eda2efbd34bed21c5e9c01e6225",
        "endpoint": "http://127.0.0.1:11434",
    },
    "invocation_command_or_surface": "aider --model ollama_chat/qwen2.5-coder:3b",
    "qualification_evidence_ref": "evidence.json",
    "telemetry_mode": {
        "identity": "exact",
        "usage": "explicit_missingness",
        "timestamps": "wall_clock",
        "raw_response_or_local_trace": "trace.jsonl",
    },
    "candidate_capture_mode": "git_diff",
    "timeout_seconds": 600,
    "network_policy": "local-loopback-plus-disabled-external",
    "retry_limit": 0,
    "escalation_limit": 0,
    "automatic_download": False,
    "implicit_fallback": False,
    "dynamic_routing": False,
    "task_context_mode": "RAW_TASK_PLUS_REPOSITORY_TOOL_ACCESS",
    "pricing_or_local_cost_ref": "local-cost-evidence",
    "frozen_at": "2026-09-16T11:00:00-03:00",
    "status": "QUALIFIED",
}


class WP04ValidatorTests(unittest.TestCase):
    def test_campaign_is_valid(self):
        self.assertEqual(validate_campaign(copy.deepcopy(CAMPAIGN)), [])

    def test_comparative_claim_is_blocked(self):
        payload = copy.deepcopy(CAMPAIGN)
        payload["scope"]["executor_ranking"] = "ALLOWED"
        self.assertTrue(any("executor_ranking" in e for e in validate_campaign(payload)))

    def test_retry_or_escalation_is_blocked(self):
        payload = copy.deepcopy(CAMPAIGN)
        payload["scope"]["retries"] = 1
        self.assertTrue(any("zero" in e for e in validate_campaign(payload)))

    def test_concrete_binding_v2_is_valid(self):
        self.assertEqual(validate_binding(copy.deepcopy(BINDING)), [])

    def test_v1_model_endpoint_binding_is_blocked(self):
        payload = copy.deepcopy(BINDING)
        payload["schema_id"] = "ndv-p1-wp04-executor-binding-v1"
        self.assertTrue(any("binding schema" in e for e in validate_binding(payload)))

    def test_missing_repository_tool_access_is_blocked(self):
        payload = copy.deepcopy(BINDING)
        payload["scaffold"]["repository_tool_access"] = False
        self.assertTrue(any("repository_tool_access" in e for e in validate_binding(payload)))

    def test_moving_binding_is_blocked(self):
        payload = copy.deepcopy(BINDING)
        payload["dynamic_routing"] = True
        payload["implicit_fallback"] = True
        errors = validate_binding(payload)
        self.assertTrue(any("dynamic_routing" in e for e in errors))
        self.assertTrue(any("implicit_fallback" in e for e in errors))

    def test_unqualified_binding_is_blocked(self):
        payload = copy.deepcopy(BINDING)
        payload["status"] = "BLOCKED"
        self.assertTrue(any("QUALIFIED" in e for e in validate_binding(payload)))


if __name__ == "__main__":
    unittest.main()
