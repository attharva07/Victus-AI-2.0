from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus

import requests


PROVIDERS = {"spotify", "youtube"}


def _load_spotify_credentials() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    client_id = None
    client_secret = None
    refresh_token = None
    spec = importlib.util.find_spec("victus_local.credentials")
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        client_id = getattr(module, "SPOTIFY_CLIENT_ID", None) or None
        client_secret = getattr(module, "SPOTIFY_CLIENT_SECRET", None) or None
        refresh_token = getattr(module, "SPOTIFY_REFRESH_TOKEN", None) or None

    client_id = client_id or os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = client_secret or os.getenv("SPOTIFY_CLIENT_SECRET")
    refresh_token = refresh_token or os.getenv("SPOTIFY_REFRESH_TOKEN")
    return client_id, client_secret, refresh_token


@dataclass
class MediaAction:
    action: str
    provider: str
    query: str
    artist: Optional[str]
    parse_confidence: float
    parse_reasons: List[str]


def parse_media_action(user_text: str) -> Optional[MediaAction]:
    normalized = user_text.strip()
    match = re.match(r"^play(?:\s+(?P<rest>.+))?$", normalized, re.IGNORECASE)
    if not match:
        return None

    rest = (match.group("rest") or "").strip()
    provider = None
    provider_explicit = False
    provider_match = re.search(r"\s+on\s+(youtube|spotify)\s*$", rest, re.IGNORECASE)
    if provider_match:
        provider = provider_match.group(1).lower()
        provider_explicit = True
        rest = rest[: provider_match.start()].strip()

    if not provider and "youtube" in rest.lower():
        provider = "youtube"
        provider_explicit = True
    provider = provider or "spotify"

    artist = None
    if " by " in rest.lower():
        parts = re.split(r"\s+by\s+", rest, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2:
            rest, artist = parts[0].strip(), parts[1].strip()

    query = rest.strip()
    if not query:
        return MediaAction(
            action="play",
            provider=provider,
            query="",
            artist=artist or None,
            parse_confidence=0.1,
            parse_reasons=["No query detected after 'play'."],
        )

    parse_confidence, parse_reasons = _score_parse(query, provider, artist, provider_explicit)
    return MediaAction(
        action="play",
        provider=provider,
        query=query,
        artist=artist or None,
        parse_confidence=parse_confidence,
        parse_reasons=parse_reasons,
    )


def _score_parse(
    query: str,
    provider: str,
    artist: Optional[str],
    provider_explicit: bool,
) -> Tuple[float, List[str]]:
    confidence = 0.4
    reasons = ["Matched 'play <query>' command."]
    if len(query) >= 3:
        confidence += 0.2
        reasons.append("Query length looks valid.")
    else:
        confidence += 0.1
        reasons.append("Query length is short but present.")
    if provider in PROVIDERS:
        if provider_explicit:
            confidence += 0.2
            reasons.append("Provider explicitly specified.")
        else:
            reasons.append("Defaulted provider to Spotify.")
    if artist:
        confidence += 0.1
        reasons.append("Detected artist segment.")
    return min(confidence, 1.0), reasons


def build_confidence(
    parse_conf: float,
    parse_reasons: List[str],
    retrieval_conf: float,
    retrieval_reasons: List[str],
) -> Dict[str, Any]:
    final = max(0.0, min(1.0, 0.55 * parse_conf + 0.45 * retrieval_conf))
    decision = _decision_from_confidence(final)
    return {
        "final": final,
        "parse": parse_conf,
        "retrieval": retrieval_conf,
        "llm": None,
        "decision": decision,
        "reasons": parse_reasons + retrieval_reasons,
    }


def _decision_from_confidence(confidence: float) -> str:
    if confidence >= 0.8:
        return "execute"
    if confidence >= 0.55:
        return "soft_confirm"
    if confidence >= 0.35:
        return "clarify"
    return "block"


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _score_retrieval(query: str, title: str, artist: Optional[str]) -> Tuple[float, List[str]]:
    query_tokens = set(_tokenize(query))
    title_tokens = set(_tokenize(title))
    if not query_tokens:
        return 0.1, ["Query tokens empty; low retrieval confidence."]
    overlap = len(query_tokens & title_tokens) / max(len(query_tokens), 1)
    confidence = 0.3 + 0.4 * overlap
    reasons = [f"Title overlap score: {overlap:.2f}."]
    if artist:
        artist_tokens = set(_tokenize(artist))
        artist_overlap = len(artist_tokens & title_tokens)
        if artist_overlap:
            confidence += 0.2
            reasons.append("Artist tokens matched title.")
    return min(confidence, 1.0), reasons


def search_youtube(query: str, api_key: str) -> Tuple[Optional[Dict[str, Any]], float, List[str]]:
    url = (
        "https://www.googleapis.com/youtube/v3/search"
        f"?part=snippet&type=video&maxResults=1&q={quote_plus(query)}&key={api_key}"
    )
    response = requests.get(url, timeout=10)
    if response.status_code != 200:
        return None, 0.1, ["YouTube search failed."]
    payload = response.json()
    items = payload.get("items") or []
    if not items:
        return None, 0.1, ["No YouTube results found."]
    item = items[0]
    video_id = item.get("id", {}).get("videoId")
    title = item.get("snippet", {}).get("title") or ""
    if not video_id:
        return None, 0.1, ["YouTube result missing videoId."]
    return {
        "video_id": video_id,
        "title": title,
    }, 0.0, []


def search_spotify(query: str, artist: Optional[str], token: str) -> Tuple[Optional[Dict[str, Any]], float, List[str]]:
    search_query = f"{query} {artist}" if artist else query
    response = requests.get(
        "https://api.spotify.com/v1/search",
        headers={"Authorization": f"Bearer {token}"},
        params={"q": search_query, "type": "track", "limit": 5},
        timeout=10,
    )
    if response.status_code != 200:
        return None, 0.1, ["Spotify search failed."]
    payload = response.json()
    items = payload.get("tracks", {}).get("items") or []
    if not items:
        return None, 0.1, ["No Spotify matches found."]

    best = items[0]
    title = best.get("name", "")
    artist_name = ", ".join([artist.get("name", "") for artist in best.get("artists", []) if artist.get("name")])
    uri = best.get("uri")
    if not uri:
        return None, 0.1, ["Spotify track missing URI."]
    return {
        "uri": uri,
        "title": title,
        "artist": artist_name,
        "url": best.get("external_urls", {}).get("spotify"),
    }, 0.0, []


def get_spotify_access_token() -> Tuple[Optional[str], Optional[str]]:
    client_id, client_secret, refresh_token = _load_spotify_credentials()
    if not client_id or not client_secret or not refresh_token:
        return None, "Spotify not configured."

    response = requests.post(
        "https://accounts.spotify.com/api/token",
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        auth=(client_id, client_secret),
        timeout=10,
    )
    if response.status_code != 200:
        return None, "Unable to refresh Spotify token."
    token = response.json().get("access_token")
    if not token:
        return None, "Spotify access token missing in response."
    return token, None


def start_spotify_playback(track_uri: str, token: str) -> Tuple[bool, Optional[str]]:
    devices_response = requests.get(
        "https://api.spotify.com/v1/me/player/devices",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    if devices_response.status_code != 200:
        return False, "Unable to query Spotify devices."
    devices = devices_response.json().get("devices") or []
    active_device = next((device for device in devices if device.get("is_active")), None)
    device_id = (active_device or (devices[0] if devices else None) or {}).get("id")
    if not device_id:
        return False, "No active Spotify device. Open Spotify desktop and play once."

    play_response = requests.put(
        "https://api.spotify.com/v1/me/player/play",
        headers={"Authorization": f"Bearer {token}"},
        json={"uris": [track_uri]},
        params={"device_id": device_id},
        timeout=10,
    )
    if play_response.status_code in {200, 204}:
        return True, None

    if play_response.status_code == 403:
        return False, "Spotify playback requires Premium."

    error_payload = play_response.json() if play_response.content else {}
    error_message = error_payload.get("error", {}).get("message")
    return False, error_message or "Unable to start Spotify playback."


def pause_spotify_playback(token: str) -> Tuple[bool, Optional[str]]:
    response = requests.put(
        "https://api.spotify.com/v1/me/player/pause",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    if response.status_code in {200, 204}:
        return True, None
    if response.status_code == 403:
        return False, "Spotify playback requires Premium."
    return False, "Unable to pause Spotify playback."


def build_now_playing(provider: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if provider == "youtube":
        video_id = payload.get("video_id")
        return {
            "provider": provider,
            "title": payload.get("title"),
            "video_id": video_id,
            "embed_url": f"https://www.youtube.com/embed/{video_id}?autoplay=1",
        }
    return {
        "provider": provider,
        "title": payload.get("title"),
        "artist": payload.get("artist"),
        "spotify_url": payload.get("url"),
    }


def run_media_play(args: Dict[str, Any]) -> Dict[str, Any]:
    action = _normalize_media_action(args)
    if not action:
        return {
            "error": "Unable to parse media command.",
            "confidence": build_confidence(0.1, ["Unable to parse command."], 0.1, []),
        }
    if not action.query:
        confidence = build_confidence(
            action.parse_confidence,
            action.parse_reasons,
            0.1,
            ["Missing track query."],
        )
        confidence["decision"] = "clarify"
        return {
            "action": action.action,
            "provider": action.provider,
            "query": action.query,
            "artist": action.artist,
            "decision": "clarify",
            "confidence": confidence,
            "assistant_message": "What would you like me to play?",
        }

    if action.provider == "youtube":
        api_key = os.getenv("YOUTUBE_API_KEY")
        if not api_key:
            return {"error": "YouTube API key is not configured."}
        result, retrieval_conf, retrieval_reasons = search_youtube(action.query, api_key)
    else:
        token, error = get_spotify_access_token()
        if error or not token:
            message = error or "Spotify not configured."
            return {
                "error": message,
                "provider": action.provider,
                "query": action.query,
                "assistant_message": message,
            }
        result, retrieval_conf, retrieval_reasons = search_spotify(action.query, action.artist, token)

    if not result:
        retrieval_conf = max(retrieval_conf, 0.1)
    retrieval_conf, retrieval_reasons = _apply_retrieval_scoring(
        action.query,
        action.artist,
        result.get("title") if result else "",
        retrieval_conf,
        retrieval_reasons,
    )
    confidence = build_confidence(
        action.parse_confidence,
        action.parse_reasons,
        retrieval_conf,
        retrieval_reasons,
    )
    if not result:
        confidence["decision"] = "clarify"
        confidence["reasons"].append("No results; requesting clarification.")
    decision = confidence["decision"]

    response: Dict[str, Any] = {
        "action": action.action,
        "provider": action.provider,
        "query": action.query,
        "artist": action.artist,
        "decision": decision,
        "confidence": confidence,
    }

    if decision == "clarify":
        response["assistant_message"] = _clarify_message(action)
        return response
    if decision == "block":
        response["assistant_message"] = "I wasn't sure what to play. Can you rephrase the request?"
        return response
    if not result:
        response["assistant_message"] = "I couldn't find a match. Could you clarify the track or artist?"
        return response

    if decision == "soft_confirm":
        response["assistant_message"] = _soft_confirm_message(action, result)

    if action.provider == "youtube":
        response["now_playing"] = build_now_playing("youtube", result)
        return response

    token, error = get_spotify_access_token()
    if error or not token:
        response["error"] = error or "Spotify not configured."
        response["assistant_message"] = response["error"]
        return response
    ok, playback_error = start_spotify_playback(result["uri"], token)
    if not ok:
        response["error"] = playback_error or "Unable to start Spotify playback."
        response["error_code"] = _spotify_error_code(playback_error or "")
        response["assistant_message"] = response["error"]
        return response
    response["now_playing"] = build_now_playing("spotify", result)
    return response


def run_media_stop(provider: str) -> Dict[str, Any]:
    if provider == "spotify":
        token, error = get_spotify_access_token()
        if error or not token:
            return {"error": error or "Spotify not configured."}
        ok, playback_error = pause_spotify_playback(token)
        if not ok:
            return {"error": playback_error or "Unable to stop Spotify playback."}
    return {"stopped": provider}


def _normalize_media_action(args: Dict[str, Any]) -> Optional[MediaAction]:
    if "query" in args or "provider" in args:
        query = str(args.get("query") or "").strip()
        provider = str(args.get("provider") or "spotify").lower()
        artist = str(args.get("artist") or "").strip() or None
        parse_confidence = float(args.get("parse_confidence") or 0.4)
        parse_reasons = list(args.get("parse_reasons") or ["Parsed media request arguments."])
        return MediaAction(
            action="play",
            provider=provider,
            query=query,
            artist=artist,
            parse_confidence=parse_confidence,
            parse_reasons=parse_reasons,
        )

    if text := args.get("text"):
        return parse_media_action(str(text))

    return None


def _apply_retrieval_scoring(
    query: str,
    artist: Optional[str],
    title: str,
    retrieval_conf: float,
    retrieval_reasons: List[str],
) -> Tuple[float, List[str]]:
    if not title:
        return retrieval_conf, retrieval_reasons
    score, reasons = _score_retrieval(query, title, artist)
    return max(retrieval_conf, score), retrieval_reasons + reasons


def _soft_confirm_message(action: MediaAction, result: Dict[str, Any]) -> str:
    title = result.get("title") or action.query
    provider = action.provider.title()
    return f"Playing {title} on {provider}..."


def _clarify_message(action: MediaAction) -> str:
    provider_hint = "Spotify or YouTube" if action.provider == "spotify" else "YouTube or Spotify"
    return f"Which provider should I use ({provider_hint}), and what track should I play?"


def _spotify_error_code(message: str) -> str:
    lowered = message.lower()
    if "premium" in lowered:
        return "premium_required"
    if "active" in lowered or "device" in lowered:
        return "no_active_device"
    return "spotify_error"
