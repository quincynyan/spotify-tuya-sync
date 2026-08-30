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


def pick_vibrant_spicetify_color(palette):
    """
    Finds the most colorful, non-grayscale swatch.
    Prioritizes chromatic energy over raw lightness.
    """
    best_color = None
    best_chroma = -1.0

    for r, g, b in palette:
        max_c = max(r, g, b)
        min_c = min(r, g, b)
        chroma = (max_c - min_c) / 255.0  # Distance from grayscale

        # Skip near-blacks and near-whites/grays
        if max_c < 30 or chroma < 0.15:
            continue

        # Score balances chroma and brightness
        score = chroma * (max_c / 255.0)

        if score > best_chroma:
            best_chroma = score
            best_color = (r, g, b)

    return best_color if best_color else palette[0]


def rgb_to_boosted_tuya_hsv(r, g, b):
    r_n, g_n, b_n = r / 255.0, g / 255.0, b / 255.0
    h, s, v = colorsys.rgb_to_hsv(r_n, g_n, b_n)

    tuya_h = int(h * 360)

    # If any noticeable color exists, force 100% saturation and full brightness
    # to disengage the white diode mixing on Tuya hardware
    if s > 0.10:
        tuya_s = 1000
        tuya_v = 1000
    else:
        tuya_s = 0
        tuya_v = int(max(200, v * 1000))

    return tuya_h, tuya_s, tuya_v


def hsv_to_hex(h, s, v):
    return f"{h:04x}{s:04x}{v:04x}"


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


def send_tuya_color(openapi, device_id, h, s, v):
    payload_v2 = {
        "commands": [
            {"code": "switch_led", "value": True},
            {"code": "work_mode", "value": "colour"},
            {"code": "colour_data_v2", "value": {"h": h, "s": s, "v": v}}
        ]
    }
    res = openapi.post(
        f"/v1.0/iot-03/devices/{device_id}/commands", payload_v2)

    if not res.get("success"):
        hex_data = hsv_to_hex(h, s, v)
        payload_hex = {
            "commands": [
                {"code": "switch_led", "value": True},
                {"code": "work_mode", "value": "colour"},
                {"code": "colour_data", "value": hex_data}
            ]
        }
        res = openapi.post(
            f"/v1.0/iot-03/devices/{device_id}/commands", payload_hex)

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
                    print(f"Now Playing: '{track_name}' by {artist}")
                    images = item["album"]["images"]

                    if images:
                        img_url = images[0]["url"]
                        img_res = requests.get(img_url, timeout=5)

                        # Extract palette of 12 candidate swatches
                        ct = ColorThief(io.BytesIO(img_res.content))
                        palette = ct.get_palette(color_count=12, quality=1)

                        # Select vibrant swatch and convert to boosted HSV
                        r, g, b = pick_vibrant_spicetify_color(palette)
                        h, s, v = rgb_to_boosted_tuya_hsv(r, g, b)

                        print(
                            f"Selected RGB({r}, {g}, {b}) -> Pure HSV({h}, {s}, {v})")
                        res = send_tuya_color(openapi, TUYA_DEVICE_ID, h, s, v)
                        print(f"Tuya Sync Status: {res.get('success')}")

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
