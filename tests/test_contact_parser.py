import unittest

from backend.services.contact_parser import normalize_email_advanced, normalize_phone_advanced


class TestContactParser(unittest.TestCase):
    def test_disposable_email_rejected(self) -> None:
        parsed = normalize_email_advanced("agent@mailinator.com")
        self.assertFalse(parsed["valid"])
        self.assertTrue(parsed["is_disposable"])
        self.assertEqual(parsed["reason"], "disposable_domain")

    def test_phone_normalization_has_value(self) -> None:
        parsed = normalize_phone_advanced("+27 44 001 0004")
        self.assertTrue(parsed["valid"])
        self.assertIsNotNone(parsed["value"])


if __name__ == "__main__":
    unittest.main()

