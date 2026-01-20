# Spotify setup (local refresh token)

This guide explains how to generate a Spotify refresh token for local use with Victus.

## 1) Create a Spotify developer app

1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
2. Create a new app and note the **Client ID** and **Client Secret**.
3. In the app settings, add this Redirect URI:

```
http://localhost:8888/callback
```

## 2) Run the helper script (PowerShell)

From the repo root, set the environment variables and run the script:

```powershell
$env:SPOTIFY_CLIENT_ID="..."
$env:SPOTIFY_CLIENT_SECRET="..."
$env:SPOTIFY_REDIRECT_URI="http://localhost:8888/callback"
python spotify_auth.py
```

The script prints an authorization URL. Open it in your browser, approve access, then paste
only the `code` value from the redirect URL back into the script.

## 3) Store the refresh token locally

Paste the printed refresh token into `victus_local/credentials.py` as `SPOTIFY_REFRESH_TOKEN`.

## Notes

- Playback control may require a Spotify Premium account and an active device.
- This script is for local use only. It does not save files or store secrets.
