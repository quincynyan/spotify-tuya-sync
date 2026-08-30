import os
import unittest

import main


class ConfigValidationTests(unittest.TestCase):
    def setUp(self):
        self.original = {
            "TUYA_ENDPOINT": os.environ.get("TUYA_ENDPOINT"),
            "TUYA_ACCESS_ID": os.environ.get("TUYA_ACCESS_ID"),
            "TUYA_ACCESS_KEY": os.environ.get("TUYA_ACCESS_KEY"),
            "TUYA_DEVICE_ID": os.environ.get("TUYA_DEVICE_ID"),
            "SPOTIFY_CLIENT_ID": os.environ.get("SPOTIFY_CLIENT_ID"),
            "SPOTIFY_CLIENT_SECRET": os.environ.get("SPOTIFY_CLIENT_SECRET"),
            "SPOTIFY_REFRESH_TOKEN": os.environ.get("SPOTIFY_REFRESH_TOKEN"),
        }

        os.environ["TUYA_ENDPOINT"] = "https://example.com"
        os.environ["TUYA_ACCESS_ID"] = "tuya-id"
        os.environ["TUYA_ACCESS_KEY"] = "tuya-key"
        os.environ["TUYA_DEVICE_ID"] = "device-id"
        os.environ["SPOTIFY_CLIENT_ID"] = "spotify-id"
        os.environ["SPOTIFY_CLIENT_SECRET"] = "spotify-secret"
        os.environ["SPOTIFY_REFRESH_TOKEN"] = "spotify-refresh"

    def tearDown(self):
        for key, value in self.original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_validate_config_accepts_required_values(self):
        main.validate_config()

    def test_validate_config_rejects_missing_values(self):
        os.environ.pop("SPOTIFY_REFRESH_TOKEN", None)

        with self.assertRaises(ValueError):
            main.validate_config()


if __name__ == "__main__":
    unittest.main()
