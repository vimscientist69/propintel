import unittest

from backend.services.scraper import (
    detect_chatbot_signal,
    detect_freshness_signal,
    latency_to_speed_score,
)


class TestScraperSignals(unittest.TestCase):
    def test_chatbot_keyword(self) -> None:
        self.assertTrue(detect_chatbot_signal("<script>chatbot</script>", ["chatbot"]))

    def test_chatbot_intercom_vendor(self) -> None:
        html = '<script src="https://widget.intercom.io/widget/abc"></script>'
        self.assertTrue(detect_chatbot_signal(html, []))

    def test_chatbot_whatsapp(self) -> None:
        self.assertTrue(
            detect_chatbot_signal('<a href="https://api.whatsapp.com/send?phone=1">Hi</a>', [])
        )

    def test_freshness_meta(self) -> None:
        html = '<meta property="article:modified_time" content="2024-01-02T00:00:00Z">'
        self.assertTrue(detect_freshness_signal(html))

    def test_freshness_last_updated_phrase(self) -> None:
        long_enough = "x" * 250
        self.assertTrue(detect_freshness_signal(f"<footer>{long_enough} last updated: Jan 2024</footer>"))

    def test_freshness_empty(self) -> None:
        self.assertFalse(detect_freshness_signal(""))

    def test_latency_to_speed_score(self) -> None:
        self.assertIsNone(latency_to_speed_score(None))
        self.assertEqual(latency_to_speed_score(200), 100)
        self.assertEqual(latency_to_speed_score(5000), 35)
        self.assertGreaterEqual(latency_to_speed_score(9000), 5)


if __name__ == "__main__":
    unittest.main()
