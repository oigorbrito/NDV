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
    "schema_id": "ndv-p1-wp04-executor-binding-v1",
    "binding_id": "x1",
    "surface_class": "LOCAL_PINNED",
    "provider_or_runtime": "runtime",
    "exact_executor_identity": "executor",
    "version_or_model_hash": "abc",
    "invocation_command_or_surface": "executor run",
    "qualification_evidence_ref": "evidence.json",
    "telemetry_mode": {
        "identity": "exact",
        "usage": "explicit_missingness",
        "timestamps": "wall_clock",
        "raw_response_or_local_trace": "trace.jsonl",
    },
    "candidate_capture_mode": "git_diff",
    "timeout_seconds": 600,
    "network_policy": "recorded",
    "retry_limit": 0,
    "escalation_limit": 0,
    "automatic_download": False,
    "implicit_fallback": False,
    "dynamic_routing": False,
    "pricing_or_local_cost_ref": "not_applicable_local",
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

    def test_concrete_binding_is_valid(self):
        self.assertEqual(validate_binding(copy.deepcopy(BINDING)), [])

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
