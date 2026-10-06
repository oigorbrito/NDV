import unittest

from tools import ndv_local_surface_probe as probe


class ClassifyTests(unittest.TestCase):
    def test_classify_environment_blocked(self):
        report = {
            "ollama": {
                "cli": {"available": False},
                "api_reachable": False,
                "models": [],
            }
        }

        self.assertEqual(
            probe.classify(report),
            {
                "status": "S0_ENVIRONMENT_BLOCKED",
                "reason": "ollama CLI not installed",
            },
        )

    def test_classify_download_required(self):
        report = {
            "ollama": {
                "cli": {"available": True},
                "api_reachable": True,
                "models": [],
            }
        }

        self.assertEqual(
            probe.classify(report),
            {
                "status": "S0_DOWNLOAD_REQUIRED",
                "reason": "runtime available but no installed model discovered",
            },
        )

    def test_classify_local_surface_discovered(self):
        report = {
            "ollama": {
                "cli": {"available": True},
                "api_reachable": True,
                "models": [{"name": "fixture-model"}, {"name": "fixture-model-2"}],
            }
        }

        self.assertEqual(
            probe.classify(report),
            {
                "status": "S0_LOCAL_SURFACE_DISCOVERED",
                "reason": "one or more installed models discovered; each model still requires executor-level qualification",
                "installed_model_count": 2,
            },
        )


if __name__ == "__main__":
    unittest.main()
