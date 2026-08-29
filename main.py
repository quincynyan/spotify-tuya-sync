import os
import time
import colorsys
import io
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from colorthief import ColorThief
from tuya_connector import TuyaOpenAPI

# Tuya Credentials
TUYA_ENDPOINT = os.getenv("TUYA_ENDPOINT", "https://openapi.tuyaeu.com")
TUYA_ACCESS_ID = os.getenv("TUYA_ACCESS_ID")
TUYA_ACCESS_KEY = os.getenv("TUYA_ACCESS_KEY")
TUYA_DEVICE_ID = os.getenv("TUYA_DEVICE_ID")

# Spotify Credentials (support both SPOTIFY_ and SPOTIPY_)
SPOTIPY_CLIENT_ID = os.getenv(
    "SPOTIFY_CLIENT_ID") or os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv(
    "SPOTIFY_CLIENT_SECRET") or os.getenv("SPOTIPY_CLIENT_SECRET")
SPOTIPY_REFRESH_TOKEN = os.getenv(
    "SPOTIFY_REFRESH_TOKEN") or os.getenv("SPOTIPY_REFRESH_TOKEN")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "3"))

# Validation check
if not all([TUYA_ACCESS_ID, TUYA_ACCESS_KEY, TUYA_DEVICE_ID]):
    raise ValueError("Missing Tuya credentials in environment variables.")
if not all([SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, SPOTIPY_REFRESH_TOKEN]):
    raise ValueError("Missing Spotify credentials in environment variables.")


def rgb_to_tuya_hsv(r, g, b):
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    tuya_h = int(h * 360)
    tuya_s = max(10, min(1000, int(s * 1000)))
    tuya_v = max(10, min(1000, int(v * 1000)))
    return tuya_h, tuya_s, tuya_v


def get_spotify_client():
    auth_manager = SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri="http://127.0.0.1:8888/callback",
        scope="user-read-playback-state",
        open_browser=False
    )
    # Generate initial access token using refresh token
    token_info = auth_manager.refresh_access_token(SPOTIPY_REFRESH_TOKEN)
    return spotipy.Spotify(auth=token_info['access_token']), auth_manager


def main():
    print("Connecting to Tuya Cloud...")
    openapi = TuyaOpenAPI(TUYA_ENDPOINT, TUYA_ACCESS_ID, TUYA_ACCESS_KEY)
    openapi.connect()
    print("Tuya Connected.")

    print("Authenticating Spotify...")
    sp, auth_manager = get_spotify_client()
    print("Spotify Connected. Polling started...")

    last_track_id = None

    while True:
        try:
            current = sp.current_playback()
            if current and current.get("is_playing") and current.get("item"):
                track_id = current["item"]["id"]
                track_name = current["item"]["name"]

                if track_id != last_track_id:
                    print(f"Now Playing: {track_name}")
                    images = current["item"]["album"]["images"]

                    if images:
                        img_url = images[0]["url"]
                        res = requests.get(img_url, timeout=5)
                        r, g, b = ColorThief(io.BytesIO(
                            res.content)).get_color(quality=1)
                        h, s, v = rgb_to_tuya_hsv(r, g, b)

                        payload = {
                            "commands": [
                                {"code": "switch_led", "value": True},
                                {"code": "work_mode", "value": "colour"},
                                {"code": "colour_data_v2", "value": {
                                    "h": h, "s": s, "v": v}}
                            ]
                        }
                        res_tuya = openapi.post(
                            f"/v1.0/iot-03/devices/{TUYA_DEVICE_ID}/commands", payload)
                        print(f"Set color HSV({h}, {s}, {v}) -> {res_tuya}")

                    last_track_id = track_id
        except Exception as e:
            print(f"Loop warning: {e}")
            # Refresh token if expired
            try:
                token_info = auth_manager.refresh_access_token(
                    SPOTIPY_REFRESH_TOKEN)
                sp = spotipy.Spotify(auth=token_info['access_token'])
            except Exception:
                pass

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
