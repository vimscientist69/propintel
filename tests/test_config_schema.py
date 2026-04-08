import unittest

from backend.core.config_schema import SourcesConfigValidationError, validate_sources_config


class TestConfigSchema(unittest.TestCase):
    def test_valid_minimal_config(self) -> None:
        cfg = {
            "input": {"strict_contact_validation": True},
            "website": {"enabled": True},
            "google_maps": {"enabled": False},
            "scoring": {"enabled": True, "weights": {}},
        }
        out = validate_sources_config(cfg)
        self.assertTrue(out["website"]["enabled"])

    def test_unknown_top_level_key_rejected(self) -> None:
        with self.assertRaises(SourcesConfigValidationError):
            validate_sources_config({"foo": {}})

    def test_unknown_weights_key_rejected(self) -> None:
        with self.assertRaises(SourcesConfigValidationError):
            validate_sources_config(
                {
                    "scoring": {
                        "enabled": True,
                        "weights": {"nonexistent_weight": 1},
                    }
                }
            )

    def test_wrong_type_rejected(self) -> None:
        with self.assertRaises(SourcesConfigValidationError):
            validate_sources_config({"website": {"enabled": "true"}})

    def test_runtime_batch_size_validation(self) -> None:
        out = validate_sources_config({"runtime": {"batch_size": 100, "stop_on_batch_error": True}})
        self.assertEqual(out["runtime"]["batch_size"], 100)
        with self.assertRaises(SourcesConfigValidationError):
            validate_sources_config({"runtime": {"batch_size": 5}})

    def test_runtime_provider_limits_validation(self) -> None:
        out = validate_sources_config(
            {
                "runtime": {
                    "worker_concurrency": 6,
                    "providers": {
                        "google_maps": {"requests_per_second": 2.0, "max_concurrent": 2},
                        "serper": {"requests_per_second": 1.5, "max_concurrent": 2},
                    },
                }
            }
        )
        self.assertEqual(out["runtime"]["worker_concurrency"], 6)
        with self.assertRaises(SourcesConfigValidationError):
            validate_sources_config(
                {"runtime": {"providers": {"google_maps": {"requests_per_second": 0}}}}
            )


if __name__ == "__main__":
    unittest.main()
