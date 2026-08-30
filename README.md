# Spotify Tuya Sync

A small Python app that watches your currently playing Spotify track and updates a Tuya smart light to match the album art's dominant color.

It polls Spotify's playback API, extracts the album artwork, finds the most vibrant accent color, and sends it to a compatible Tuya device using a color command payload.

## Features

- Tracks the currently playing Spotify song
- Reads the album art from the active track
- Detects a vibrant accent color from the image
- Sends the color to a Tuya smart light
- Runs as a simple long-lived background process
- Works locally or in Docker

## Project structure

```text
spotify-tuya-sync/
├── main.py
├── get-token.py
├── requirements.txt
├── Dockerfile
├── .gitignore
├── .env.example
├── README.md
└── .env
```

## Requirements

- Python 3.11+
- A Spotify Developer app
- A Tuya device and API credentials
- A networked Tuya-compatible smart light

## Setup

1. Clone the repo.
2. Create a virtual environment.
3. Install dependencies.

```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Environment variables

Create a `.env` file in the project root with the following values:

```env
TUYA_ENDPOINT=https://openapi-sg.iotbing.com
TUYA_ACCESS_ID=your_tuya_access_id
TUYA_ACCESS_KEY=your_tuya_access_key
TUYA_DEVICE_ID=your_tuya_device_id

SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
SPOTIFY_REFRESH_TOKEN=your_spotify_refresh_token

POLL_INTERVAL=3
```

> The Tuya endpoint can vary by region. For some users it may be something like `https://openapi-us.iotbing.com` or another regional endpoint instead of the default Singapore endpoint.

## Get your Spotify refresh token

Use the helper script:

```bash
python get-token.py
```

This prints a Spotify authorization URL and then the refresh token to use in `.env`.

## Run locally

```bash
python main.py
```

The script will keep polling Spotify and update the light whenever the current track changes.

## Run with Docker

```bash
docker build -t spotify-tuya-sync .
docker run --env-file .env spotify-tuya-sync
```

## Notes

- The script only updates when a track changes, not on every poll.
- If Spotify playback is paused or empty, it does nothing.
- `SPOTIFY_REFRESH_TOKEN` is required for non-interactive refresh-based auth.
- Tuya payloads can vary slightly by device model and product type, so some devices may need slight adjustment in the command payload.

## License

This project is provided as-is for personal use and experimentation.

