import os
import time
import colorsys
import io
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from colorthief import ColorThief
from tuya_connector import TuyaOpenAPI

# Load credentials from Environment Variables
TUYA_ENDPOINT = os.getenv("TUYA_ENDPOINT", "https://openapi.tuyaeu.com")
TUYA_ACCESS_ID = os.getenv("TUYA_ACCESS_ID")
TUYA_ACCESS_KEY = os.getenv("TUYA_ACCESS_KEY")
TUYA_DEVICE_ID = os.getenv("TUYA_DEVICE_ID")

SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
SPOTIPY_REDIRECT_URI = os.getenv(
    "SPOTIPY_REDIRECT_URI", "http://localhost:8080")
SPOTIPY_REFRESH_TOKEN = os.getenv("SPOTIPY_REFRESH_TOKEN")

POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "3"))


def rgb_to_tuya_hsv(r, g, b):
    """Converts 0-255 RGB to Tuya v2 scale: H (0-360), S (10-1000), V (10-1000)"""
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    tuya_h = int(h * 360)
    tuya_s = max(10, min(1000, int(s * 1000)))
    tuya_v = max(10, min(1000, int(v * 1000)))
    return tuya_h, tuya_s, tuya_v


def main():
    # 1. Initialize Tuya Cloud API
    openapi = TuyaOpenAPI(TUYA_ENDPOINT, TUYA_ACCESS_ID, TUYA_ACCESS_KEY)
    openapi.connect()
    print("Connected to Tuya Cloud.")

    # 2. Initialize Spotify Client
    auth_manager = SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=SPOTIPY_REDIRECT_URI,
        scope="user-read-playback-state"
    )

    # Inject pre-generated refresh token if provided
    if SPOTIPY_REFRESH_TOKEN:
        auth_manager.refresh_access_token(SPOTIPY_REFRESH_TOKEN)

    sp = spotipy.Spotify(auth_manager=auth_manager)
    print("Spotify listener initialized. Starting loop...")

    last_track_id = None

    while True:
        try:
            current = sp.current_playback()
            if current and current.get("is_playing") and current.get("item"):
                track_id = current["item"]["id"]
                track_name = current["item"]["name"]

                if track_id != last_track_id:
                    print(f"Track changed: {track_name}")
                    images = current["item"]["album"]["images"]

                    if images:
                        img_url = images[0]["url"]
                        res = requests.get(img_url, timeout=5)
                        palette = ColorThief(io.BytesIO(
                            res.content)).get_color(quality=1)
                        r, g, b = palette
                        h, s, v = rgb_to_tuya_hsv(r, g, b)

                        # Send commands to bulb via Tuya OpenAPI
                        commands = {
                            "commands": [
                                {"code": "switch_led", "value": True},
                                {"code": "work_mode", "value": "colour"},
                                {"code": "colour_data_v2", "value": {
                                    "h": h, "s": s, "v": v}}
                            ]
                        }
                        res = openapi.post(
                            f"/v1.0/devices/{TUYA_DEVICE_ID}/commands", commands)
                        print(
                            f"Sent color H:{h} S:{s} V:{v} -> Status: {res.get('success')}")

                    last_track_id = track_id

        except Exception as err:
            print(f"Loop warning: {err}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
