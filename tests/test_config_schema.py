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


if __name__ == "__main__":
    unittest.main()
