import unittest
from pathlib import Path

from app.config import DEFAULT_PROFILE_PATH, load_settings


class LoadSettingsTests(unittest.TestCase):
    def test_defaults_when_environment_is_empty(self):
        settings = load_settings({})

        self.assertEqual(settings.max_file_bytes, 10_485_760)
        self.assertEqual(settings.max_text_bytes, 5_242_880)
        self.assertEqual(settings.max_sync_pages, 100)
        self.assertEqual(settings.fallback_encoding, "cp1252")
        self.assertEqual(settings.di_timeout_seconds, 90)
        self.assertEqual(settings.profile_path, DEFAULT_PROFILE_PATH)
        self.assertIsNone(settings.document_intelligence_endpoint)

    def test_integer_override_is_parsed(self):
        settings = load_settings({"SANITIZER_MAX_FILE_BYTES": "2048"})

        self.assertEqual(settings.max_file_bytes, 2048)

    def test_endpoint_and_profile_path_are_read(self):
        settings = load_settings(
            {
                "DOCUMENT_INTELLIGENCE_ENDPOINT": "https://example.cognitiveservices.azure.com/",
                "SANITIZER_PROFILE_PATH": "/tmp/profiles.json",
            }
        )

        self.assertEqual(
            settings.document_intelligence_endpoint,
            "https://example.cognitiveservices.azure.com/",
        )
        self.assertEqual(settings.profile_path, Path("/tmp/profiles.json"))

    def test_non_integer_value_raises(self):
        with self.assertRaises(ValueError):
            load_settings({"SANITIZER_MAX_SYNC_PAGES": "abc"})

    def test_negative_value_raises(self):
        with self.assertRaises(ValueError):
            load_settings({"SANITIZER_MAX_TEXT_BYTES": "-1"})


if __name__ == "__main__":
    unittest.main()
