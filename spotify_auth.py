import base64
import os
import urllib.parse

import requests


CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback")

SCOPES = [
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-read-currently-playing",
]


def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        raise SystemExit(
            "Missing env vars. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET first."
        )

    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "scope": " ".join(SCOPES),
        "redirect_uri": REDIRECT_URI,
    }
    auth_url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(params)

    print("\n1) Open this URL in your browser and approve access:\n")
    print(auth_url)
    print("\n2) After approval, Spotify will redirect you to:")
    print("   http://localhost:8888/callback?code=...")
    code = input("\nPaste ONLY the 'code' value here: ").strip()

    token_url = "https://accounts.spotify.com/api/token"
    basic = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode("utf-8")).decode(
        "utf-8"
    )
    headers = {"Authorization": f"Basic {basic}"}
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }

    r = requests.post(token_url, headers=headers, data=data, timeout=30)
    print("\nStatus:", r.status_code)
    if r.status_code != 200:
        print("Response:\n", r.text)
        raise SystemExit(
            "Token exchange failed. Check redirect URI, client secret, and code."
        )

    payload = r.json()
    refresh = payload.get("refresh_token")
    if not refresh:
        print("\nFull response:\n", payload)
        raise SystemExit(
            "No refresh_token returned. Re-authorize and ensure scopes are correct."
        )

    print("\n✅ SUCCESS")
    print("REFRESH TOKEN (save this):\n")
    print(refresh)
    print("\nPaste this into victus_local/credentials.py as SPOTIFY_REFRESH_TOKEN.\n")


if __name__ == "__main__":
    main()
