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
TUYA_ENDPOINT = "https://openapi-sg.iotbing.com"
TUYA_ACCESS_ID = None
TUYA_ACCESS_KEY = None
TUYA_DEVICE_ID = None

# Spotify Credentials
SPOTIFY_CLIENT_ID = None
SPOTIFY_CLIENT_SECRET = None
SPOTIFY_REFRESH_TOKEN = None
POLL_INTERVAL = 3


def refresh_config():
    global TUYA_ENDPOINT, TUYA_ACCESS_ID, TUYA_ACCESS_KEY, TUYA_DEVICE_ID
    global SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REFRESH_TOKEN, POLL_INTERVAL

    TUYA_ENDPOINT = os.getenv("TUYA_ENDPOINT", TUYA_ENDPOINT)
    TUYA_ACCESS_ID = os.getenv("TUYA_ACCESS_ID")
    TUYA_ACCESS_KEY = os.getenv("TUYA_ACCESS_KEY")
    TUYA_DEVICE_ID = os.getenv("TUYA_DEVICE_ID")

    SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
    SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
    SPOTIFY_REFRESH_TOKEN = os.getenv("SPOTIFY_REFRESH_TOKEN")
    POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", str(POLL_INTERVAL)))


def validate_config():
    refresh_config()

    missing = []
    for name, value in {
            "TUYA_ACCESS_ID": TUYA_ACCESS_ID,
            "TUYA_ACCESS_KEY": TUYA_ACCESS_KEY,
            "TUYA_DEVICE_ID": TUYA_DEVICE_ID,
            "SPOTIFY_CLIENT_ID": SPOTIFY_CLIENT_ID,
            "SPOTIFY_CLIENT_SECRET": SPOTIFY_CLIENT_SECRET,
            "SPOTIFY_REFRESH_TOKEN": SPOTIFY_REFRESH_TOKEN,
    }.items():
        if not value:
            missing.append(name)

    if missing:
        raise ValueError(
            "Missing required environment variables: " + ", ".join(missing)
        )


def require_config_value(name: str, value: str | None) -> str:
    if value is None or value == "":
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def get_vibrant_color_from_image(img_bytes: bytes) -> tuple[int, int, int]:
    """
    Directly analyzes raw pixels with PIL and picks the most colorful accent.
    """
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    img = img.resize((64, 64))  # Downsample for fast processing

    width, height = img.size
    pixels: list[tuple[int, int, int]] = []
    for y in range(height):
        for x in range(width):
            pixel = img.getpixel((x, y))
            if isinstance(pixel, tuple):
                pixels.append((int(pixel[0]), int(pixel[1]), int(pixel[2])))

    best_color: tuple[int, int, int] | None = None
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

    if best_color is None:
        # Fallback to center crop if fully muted
        w, h = img.size
        pixel = img.getpixel((w // 2, h // 2))
        if isinstance(pixel, tuple):
            best_color = (int(pixel[0]), int(pixel[1]), int(pixel[2]))
        else:
            best_color = (0, 0, 0)

    assert best_color is not None
    return best_color


def hsv_to_tuya_hex(h, s, v):
    """Formats to Tuya standard 12-char hex string: HHHHSSSSVVVV (0-360, 0-1000, 0-1000)."""
    return f"{int(h):04x}{int(s):04x}{int(v):04x}"


def get_spotify_client():
    refresh_config()
    client_id = require_config_value("SPOTIFY_CLIENT_ID", SPOTIFY_CLIENT_ID)
    client_secret = require_config_value(
        "SPOTIFY_CLIENT_SECRET", SPOTIFY_CLIENT_SECRET
    )
    refresh_token = require_config_value(
        "SPOTIFY_REFRESH_TOKEN", SPOTIFY_REFRESH_TOKEN
    )

    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri="http://127.0.0.1:8888/callback",
        scope="user-read-playback-state",
        open_browser=False,
    )
    token_info = auth_manager.refresh_access_token(refresh_token)
    return spotipy.Spotify(auth=token_info["access_token"]), auth_manager


def send_tuya_color(openapi, device_id, r, g, b):
    # Calculate pure HSV values
    h_norm, _, _ = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    tuya_h = int(h_norm * 360)
    tuya_s = 1000
    tuya_v = 1000

    hex_data = hsv_to_tuya_hex(tuya_h, tuya_s, tuya_v)

    commands_list = [
        {"code": "switch_led", "value": True},
        {"code": "work_mode", "value": "colour"},
        {"code": "colour_data", "value": hex_data},
    ]

    payload = {"commands": commands_list}
    res = openapi.post(f"/v1.0/iot-03/devices/{device_id}/commands", payload)
    print(
        f"Tuya command sent -> HSV({tuya_h}, {tuya_s}, {tuya_v}) | Resp: {res}")
    return res


def main():
    refresh_config()
    validate_config()

    tuya_endpoint = require_config_value("TUYA_ENDPOINT", TUYA_ENDPOINT)
    tuya_access_id = require_config_value("TUYA_ACCESS_ID", TUYA_ACCESS_ID)
    tuya_access_key = require_config_value("TUYA_ACCESS_KEY", TUYA_ACCESS_KEY)
    tuya_device_id = require_config_value("TUYA_DEVICE_ID", TUYA_DEVICE_ID)

    print("Connecting to Tuya Cloud...")
    openapi = TuyaOpenAPI(tuya_endpoint, tuya_access_id, tuya_access_key)
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
