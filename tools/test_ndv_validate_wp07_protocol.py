import copy
import json
import unittest
from pathlib import Path

import ndv_validate_wp07_protocol as mod


class WP07ProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol = json.loads((Path(__file__).parents[1] / "experiments" / "p1" / "wp07-development-comparison-protocol-v1.json").read_text(encoding="utf-8"))

    def test_frozen_protocol_passes(self):
        self.assertEqual(mod.validate(self.protocol), [])

    def test_dynamic_router_is_rejected(self):
        p = copy.deepcopy(self.protocol)
        p["treatments"]["B2"]["dynamic_routing"] = True
        self.assertTrue(any("dynamic routing" in e for e in mod.validate(p)))

    def test_holdout_scope_expansion_is_rejected(self):
        p = copy.deepcopy(self.protocol)
        p["execution_release"]["sealed_holdout_access"] = True
        self.assertTrue(any("scope too broad" in e for e in mod.validate(p)))

    def test_missing_failure_cost_accounting_is_rejected(self):
        p = copy.deepcopy(self.protocol)
        p["accounting"]["failure_cost_retained"] = False
        self.assertTrue(any("failure_cost_retained" in e for e in mod.validate(p)))

    def test_post_hoc_model_selection_cannot_become_escalation_trigger(self):
        p = copy.deepcopy(self.protocol)
        p["forbidden_escalation_triggers"].remove("POST_HOC_MODEL_SELECTION")
        p["escalation_triggers"].append("POST_HOC_MODEL_SELECTION")
        errors = mod.validate(p)
        self.assertTrue(any("escalation triggers drift" in e for e in errors))
        self.assertTrue(any("forbidden escalation" in e for e in errors))

    def test_multiple_s2_repetitions_are_rejected_before_variance_review(self):
        p = copy.deepcopy(self.protocol)
        p["s2_rollout_policy"]["repetitions_per_cell"] = 3
        self.assertTrue(any("one rollout" in e for e in mod.validate(p)))


if __name__ == "__main__":
    unittest.main()
