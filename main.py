import os
import time
import colorsys
import io

from dotenv import load_dotenv
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from PIL import Image
from tuya_connector import TuyaOpenAPI

load_dotenv()

# Tuya Credentials
TUYA_ENDPOINT = os.getenv("TUYA_ENDPOINT", "https://openapi-sg.iotbing.com")
TUYA_ACCESS_ID = os.getenv("TUYA_ACCESS_ID")
TUYA_ACCESS_KEY = os.getenv("TUYA_ACCESS_KEY")
TUYA_DEVICE_ID = os.getenv("TUYA_DEVICE_ID")

# Spotify Credentials
SPOTIFY_CLIENT_ID = os.getenv(
    "SPOTIFY_CLIENT_ID") or os.getenv("SPOTIPY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv(
    "SPOTIFY_CLIENT_SECRET") or os.getenv("SPOTIPY_CLIENT_SECRET")
SPOTIFY_REFRESH_TOKEN = os.getenv(
    "SPOTIFY_REFRESH_TOKEN") or os.getenv("SPOTIPY_REFRESH_TOKEN")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "3"))


def get_vibrant_color_from_image(img_bytes):
    """
    Directly analyzes raw pixels with PIL and picks the most colorful accent.
    """
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    img = img.resize((64, 64))  # Downsample for fast processing

    pixels = list(img.get_flattened_data()) if hasattr(
        img, "get_flattened_data") else list(img.getdata())
    best_color = None
    max_score = -1.0

    for r, g, b in pixels:
        max_c = max(r, g, b)
        min_c = min(r, g, b)
        chroma = (max_c - min_c) / 255.0  # Colorfulness

        # Ignore blacks, muddy shadows, and near-white/pale gray backgrounds
        if max_c < 40 or min_c > 220 or chroma < 0.25:
            continue

        h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)

        # Score heavily rewarding saturation
        score = (s ** 2.5) * (1.0 - abs(l - 0.50))

        if score > max_score:
            max_score = score
            best_color = (r, g, b)

    if not best_color:
        # Fallback to center crop if fully muted
        w, h = img.size
        best_color = img.getpixel((w // 2, h // 2))

    return best_color


def hsv_to_tuya_hex(h, s, v):
    """Formats to Tuya standard 12-char hex string: HHHHSSSSVVVV (0-360, 0-1000, 0-1000)."""
    return f"{int(h):04x}{int(s):04x}{int(v):04x}"


def get_spotify_client():
    auth_manager = SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri="http://127.0.0.1:8888/callback",
        scope="user-read-playback-state",
        open_browser=False
    )
    token_info = auth_manager.refresh_access_token(SPOTIFY_REFRESH_TOKEN)
    return spotipy.Spotify(auth=token_info['access_token']), auth_manager


def send_tuya_color(openapi, device_id, r, g, b):
    # Calculate pure HSV values
    h_norm, s_norm, v_norm = colorsys.rgb_to_hsv(
        r / 255.0, g / 255.0, b / 255.0)
    tuya_h = int(h_norm * 360)
    tuya_s = 1000  # Lock to max saturation to kill white bleed
    tuya_v = 1000  # Max brightness

    hex_data = hsv_to_tuya_hex(tuya_h, tuya_s, tuya_v)

    # Universal payload explicitly setting work_mode and testing all Tuya DP codes
    commands_list = [
        {"code": "switch_led", "value": True},
        {"code": "work_mode", "value": "colour"},
        {"code": "colour_data_v2", "value": {
            "h": tuya_h, "s": tuya_s, "v": tuya_v}},
        {"code": "colour_data", "value": hex_data}
    ]

    payload = {"commands": commands_list}
    res = openapi.post(f"/v1.0/iot-03/devices/{device_id}/commands", payload)
    print(
        f"Tuya command sent -> HSV({tuya_h}, {tuya_s}, {tuya_v}) | Resp: {res}")
    return res


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
            if not current:
                time.sleep(POLL_INTERVAL)
                continue

            is_playing = current.get("is_playing", False)
            item = current.get("item")

            if is_playing and item:
                track_id = item["id"]
                track_name = item["name"]

                if track_id != last_track_id:
                    artist = item['artists'][0]['name']
                    print(f"\n--- Track: '{track_name}' by {artist} ---")
                    images = item["album"]["images"]

                    if images:
                        img_url = images[0]["url"]
                        img_res = requests.get(img_url, timeout=5)

                        r, g, b = get_vibrant_color_from_image(img_res.content)
                        print(f"Target Pure RGB: ({r}, {g}, {b})")

                        send_tuya_color(openapi, TUYA_DEVICE_ID, r, g, b)

                    last_track_id = track_id
        except Exception as e:
            print(f"Loop notice: {e}")
            try:
                token_info = auth_manager.refresh_access_token(
                    SPOTIFY_REFRESH_TOKEN)
                sp = spotipy.Spotify(auth=token_info['access_token'])
            except Exception:
                pass

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
