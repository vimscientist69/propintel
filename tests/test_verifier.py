import unittest

from backend.services.verifier import compute_contact_quality, verify_lead


class TestVerifier(unittest.TestCase):
    # --- Disposable / bad email ---

    def test_disposable_email_is_low_without_valid_phone(self) -> None:
        q, ver = compute_contact_quality("agent@mailinator.com", None)
        self.assertEqual(q, "low")
        self.assertFalse(ver["email"]["valid"])
        self.assertEqual(ver["email"]["reason"], "disposable_domain")
        self.assertTrue(ver["email"]["is_disposable"])

    def test_another_disposable_domain(self) -> None:
        q, _ = compute_contact_quality("x@yopmail.com", "not-a-real-phone-123")
        self.assertEqual(q, "low")

    def test_disposable_email_but_valid_phone_is_likely(self) -> None:
        """Email rejected; phone counts as the one valid channel."""
        q, ver = compute_contact_quality("bad@tempmail.com", "+27825550199")
        self.assertEqual(q, "likely")
        self.assertFalse(ver["email"]["valid"])
        self.assertTrue(ver["phone"]["valid"])

    # --- Invalid email format ---

    def test_malformed_email_no_at(self) -> None:
        q, ver = compute_contact_quality("not-an-email", None)
        self.assertEqual(q, "low")
        self.assertEqual(ver["email"]["reason"], "invalid_format")

    def test_malformed_email_with_valid_phone_is_likely(self) -> None:
        q, _ = compute_contact_quality("not-an-email", "+27825550199")
        self.assertEqual(q, "likely")

    # --- Valid email variety ---

    def test_email_case_normalized_in_verification(self) -> None:
        _, ver = compute_contact_quality("Hello@Acme.CO.Za", "+27825550199")
        self.assertEqual(ver["email"]["normalized"], "hello@acme.co.za")

    def test_role_prefix_email_still_valid_with_phone_verified(self) -> None:
        q, ver = compute_contact_quality("info@acmerealty.co.za", "+27123456789")
        self.assertEqual(q, "verified")
        self.assertTrue(ver["email"]["valid"])

    def test_valid_email_only_is_likely(self) -> None:
        q, _ = compute_contact_quality("person@example.com", None)
        self.assertEqual(q, "likely")

    # --- Phone variety ---

    def test_valid_email_and_mobile_verified(self) -> None:
        q, ver = compute_contact_quality("hello@acme.co.za", "+27825550199")
        self.assertEqual(q, "verified")
        self.assertTrue(ver["phone"]["valid"])
        self.assertEqual(ver["phone"]["normalized"], "+27825550199")

    def test_phone_with_spaces_still_valid(self) -> None:
        q, ver = compute_contact_quality("a@b.co", "+27 82 555 0199")
        self.assertEqual(q, "verified")
        self.assertTrue(ver["phone"]["valid"])

    def test_phone_only_valid_is_likely(self) -> None:
        q, _ = compute_contact_quality(None, "+27825550199")
        self.assertEqual(q, "likely")

    def test_invalid_phone_too_short(self) -> None:
        q, ver = compute_contact_quality(None, "12345")
        self.assertEqual(q, "low")
        self.assertFalse(ver["phone"]["valid"])

    # --- International phones (E.164; phonenumbers validates globally) ---

    def test_phone_united_states_verified(self) -> None:
        q, ver = compute_contact_quality("us@example.com", "+14155552671")
        self.assertEqual(q, "verified")
        self.assertTrue(ver["phone"]["valid"])
        self.assertTrue(ver["phone"]["normalized"].startswith("+1"))

    def test_phone_united_kingdom_verified(self) -> None:
        q, ver = compute_contact_quality("uk@example.com", "+442071838750")
        self.assertEqual(q, "verified")
        self.assertTrue(ver["phone"]["valid"])
        self.assertTrue(ver["phone"]["normalized"].startswith("+44"))

    def test_phone_germany_verified(self) -> None:
        q, ver = compute_contact_quality("de@example.com", "+493012345678")
        self.assertEqual(q, "verified")
        self.assertTrue(ver["phone"]["valid"])
        self.assertTrue(ver["phone"]["normalized"].startswith("+49"))

    def test_phone_australia_verified(self) -> None:
        q, ver = compute_contact_quality("au@example.com", "+61412345678")
        self.assertEqual(q, "verified")
        self.assertTrue(ver["phone"]["valid"])
        self.assertTrue(ver["phone"]["normalized"].startswith("+61"))

    def test_phone_india_verified(self) -> None:
        q, ver = compute_contact_quality("in@example.com", "+919876543210")
        self.assertEqual(q, "verified")
        self.assertTrue(ver["phone"]["valid"])
        self.assertTrue(ver["phone"]["normalized"].startswith("+91"))

    def test_phone_brazil_verified(self) -> None:
        q, ver = compute_contact_quality("br@example.com", "+5511987654321")
        self.assertEqual(q, "verified")
        self.assertTrue(ver["phone"]["valid"])
        self.assertTrue(ver["phone"]["normalized"].startswith("+55"))

    def test_phone_france_verified(self) -> None:
        q, ver = compute_contact_quality("fr@example.com", "+33142222222")
        self.assertEqual(q, "verified")
        self.assertTrue(ver["phone"]["valid"])
        self.assertTrue(ver["phone"]["normalized"].startswith("+33"))

    def test_phone_japan_verified(self) -> None:
        q, ver = compute_contact_quality("jp@example.com", "+819012345678")
        self.assertEqual(q, "verified")
        self.assertTrue(ver["phone"]["valid"])
        self.assertTrue(ver["phone"]["normalized"].startswith("+81"))

    def test_phone_mexico_verified(self) -> None:
        q, ver = compute_contact_quality("mx@example.com", "+525512345678")
        self.assertEqual(q, "verified")
        self.assertTrue(ver["phone"]["valid"])
        self.assertTrue(ver["phone"]["normalized"].startswith("+52"))

    def test_phone_nigeria_verified(self) -> None:
        q, ver = compute_contact_quality("ng@example.com", "+2348012345678")
        self.assertEqual(q, "verified")
        self.assertTrue(ver["phone"]["valid"])
        self.assertTrue(ver["phone"]["normalized"].startswith("+234"))

    # --- Empty / whitespace edge cases ---

    def test_none_none_is_low(self) -> None:
        q, _ = compute_contact_quality(None, None)
        self.assertEqual(q, "low")

    def test_empty_strings_are_low(self) -> None:
        q, ver = compute_contact_quality("", "")
        self.assertEqual(q, "low")
        self.assertEqual(ver["email"]["reason"], "empty_email")
        self.assertEqual(ver["phone"]["reason"], "empty_phone")

    def test_whitespace_only_email_stripped_to_empty(self) -> None:
        q, _ = compute_contact_quality("   ", None)
        self.assertEqual(q, "low")

    # --- Both invalid ---

    def test_both_channels_invalid_is_low(self) -> None:
        q, _ = compute_contact_quality("@@@", "12")
        self.assertEqual(q, "low")

    # --- verify_lead ---

    def test_verify_lead_sets_contact_quality_and_verification(self) -> None:
        out = verify_lead({"email": "a@b.co", "phone": "+27123456789"})
        self.assertIn("contact_quality", out)
        self.assertIn("verification", out)
        self.assertIn("email", out["verification"])
        self.assertIn("phone", out["verification"])

    def test_verify_lead_missing_email_phone_keys(self) -> None:
        out = verify_lead({"company_name": "X"})
        self.assertEqual(out["contact_quality"], "low")

    def test_verify_lead_in_place_mutates_original(self) -> None:
        lead: dict = {"email": "x@y.co", "phone": "+27825550199"}
        original_id = id(lead)
        returned = verify_lead(lead, in_place=True)
        self.assertIs(returned, lead)
        self.assertEqual(id(lead), original_id)
        self.assertEqual(lead["contact_quality"], "verified")

    def test_verify_lead_copy_when_not_in_place(self) -> None:
        lead = {"email": "x@y.co", "phone": "+27825550199"}
        out = verify_lead(lead, in_place=False)
        self.assertIsNot(out, lead)
        self.assertNotIn("contact_quality", lead)


if __name__ == "__main__":
    unittest.main()