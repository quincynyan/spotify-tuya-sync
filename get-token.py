# get_token.py
import os

import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

# Create a .env file in this project directory with:
# SPOTIFY_CLIENT_ID=your_spotify_client_id
# SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
load_dotenv()

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
    raise RuntimeError(
        "Missing Spotify credentials. Add SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET to your .env file."
    )

REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPE = "user-read-playback-state"

auth = SpotifyOAuth(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
    scope=SCOPE,
)

print("\nCopy and paste this into your browser if it doesn't open automatically:")
print(auth.get_authorize_url())

token_info = auth.get_access_token()
print("\n" + "=" * 50)
print("YOUR SPOTIFY REFRESH TOKEN:")
print(token_info["refresh_token"])
print("=" * 50)
