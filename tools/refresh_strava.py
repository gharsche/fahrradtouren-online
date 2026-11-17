#!/usr/bin/env python3
"""Refresh Strava activities; persist rotated refresh token encrypted before continuing."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIVITIES_PATH = ROOT / "content" / "strava-latest-activities.json"
MAP_URL_PATH = ROOT / "content" / "strava-latest-map-url.txt"
ENCRYPTED_TOKEN_PATH = ROOT / "content" / "strava-refresh-token.enc"
TOKEN_URL = "https://www.strava.com/oauth/token"
ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"


def _token_box(encryption_key: str):
    try:
        from nacl.secret import SecretBox
    except ImportError:
        raise RuntimeError("PyNaCl is required to encrypt the rotated Strava token") from None
    if len(encryption_key) < 32:
        raise RuntimeError("STRAVA_TOKEN_ENCRYPTION_KEY must be at least 32 characters")
    return SecretBox(hashlib.sha256(encryption_key.encode("utf-8")).digest())


def _run_git(*args: str) -> None:
    try:
        subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError:
        raise RuntimeError("Could not persist encrypted refresh-token rotation to the repository") from None


def _preflight(encryption_key: str) -> None:
    _token_box(encryption_key)
    if os.environ.get("GITHUB_ACTIONS") == "true":
        _run_git("push", "--dry-run", "origin", "HEAD:main")


def _post_form(url: str, fields: dict[str, str]) -> dict:
    request = urllib.request.Request(url, data=urllib.parse.urlencode(fields).encode(), headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Strava returned HTTP {exc.code} for token refresh") from None


def _get_json(url: str, access_token: str) -> list[dict]:
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Strava returned HTTP {exc.code} while reading activities") from None


def _atomic_write(path: Path, content: str) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def _read_refresh_token(encryption_key: str) -> str:
    if ENCRYPTED_TOKEN_PATH.is_file():
        try:
            return _token_box(encryption_key).decrypt(base64.b64decode(ENCRYPTED_TOKEN_PATH.read_text(encoding="utf-8").strip())).decode("utf-8")
        except Exception:
            raise RuntimeError("Could not decrypt stored Strava refresh token; refusing refresh") from None
    token = os.environ.get("STRAVA_REFRESH_TOKEN", "")
    if not token:
        raise RuntimeError("No encrypted or bootstrap STRAVA_REFRESH_TOKEN is available")
    return token


def _persist_rotated_token(token: str, encryption_key: str) -> None:
    encrypted = base64.b64encode(_token_box(encryption_key).encrypt(token.encode("utf-8"))).decode("ascii") + "\n"
    _atomic_write(ENCRYPTED_TOKEN_PATH, encrypted)
    if os.environ.get("GITHUB_ACTIONS") == "true":
        try:
            subprocess.run(["git", "add", str(ENCRYPTED_TOKEN_PATH.relative_to(ROOT))], cwd=ROOT, check=True, capture_output=True, text=True)
            subprocess.run(["git", "-c", "user.name=github-actions[bot]", "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com", "commit", "-m", "Persist encrypted Strava token rotation"], cwd=ROOT, check=True, capture_output=True, text=True)
            for attempt in range(3):
                try:
                    if attempt:
                        subprocess.run(["git", "pull", "--rebase", "origin", "main"], cwd=ROOT, check=True, capture_output=True, text=True)
                    subprocess.run(["git", "push", "origin", "HEAD:main"], cwd=ROOT, check=True, capture_output=True, text=True)
                    break
                except subprocess.CalledProcessError:
                    if attempt == 2:
                        raise
        except subprocess.CalledProcessError:
            raise RuntimeError("Could not persist encrypted Strava token rotation; stop and re-authorize before another refresh") from None


def format_activity(activity: dict) -> list[str]:
    activity_id = int(activity["id"])
    date_value = datetime.fromisoformat(activity["start_date_local"].replace("Z", "+00:00"))
    distance_text = f"{float(activity.get('distance', 0)) / 1000:.2f}".replace(".", ",")
    moving_seconds = int(activity.get("moving_time", 0))
    hours, remainder = divmod(moving_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    elevation = int(Decimal(str(activity.get("total_elevation_gain", 0))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    calories = int(Decimal(str(activity.get("calories", 0) or 0)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    summary = f"{date_value:%d.%m.%Y} · {distance_text} km · {hours}:{minutes:02d}:{seconds:02d} h · {elevation} hm"
    if calories:
        summary += f" · {calories:,}".replace(",", ".") + " kcal"
    return [str(activity.get("name", "Strava-Aktivität")), f"https://www.strava.com/activities/{activity_id}", summary]


def render_activity_json(activities: list[dict], map_url: str | None = None) -> str:
    return json.dumps({"activities": [format_activity(item) for item in activities], "map_url": map_url}, ensure_ascii=False, indent=2) + "\n"


def _validate_activities(activities: object) -> list[dict]:
    if not isinstance(activities, list) or not activities:
        raise RuntimeError("Strava activities response was empty or not a list; keeping last good data")
    for activity in activities:
        if not isinstance(activity, dict) or not all(key in activity for key in ("id", "name", "start_date_local")):
            raise RuntimeError("Strava activities response contained an invalid activity")
        try:
            int(activity["id"])
            datetime.fromisoformat(str(activity["start_date_local"]).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            raise RuntimeError("Strava activities response contained an invalid id or date") from None
    return activities


def _update_map(activity: dict) -> str:
    current = MAP_URL_PATH.read_text(encoding="utf-8").strip()
    parsed = urllib.parse.urlsplit(current)
    if parsed.netloc != "maps.googleapis.com":
        raise RuntimeError("Configured Strava map is not a Google Static Maps URL")
    polyline = activity.get("map", {}).get("summary_polyline")
    if not polyline:
        return current
    params = [(key, value) for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True) if key not in {"path", "size"}]
    params.extend([("size", "600x400"), ("path", f"weight:4|color:0xFC5200|enc:{polyline}")])
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(params), ""))


def refresh() -> int:
    client_id = os.environ["STRAVA_CLIENT_ID"]
    client_secret = os.environ["STRAVA_CLIENT_SECRET"]
    encryption_key = os.environ["STRAVA_TOKEN_ENCRYPTION_KEY"]
    _preflight(encryption_key)
    old_refresh = _read_refresh_token(encryption_key)
    token_data = _post_form(TOKEN_URL, {"client_id": client_id, "client_secret": client_secret, "grant_type": "refresh_token", "refresh_token": old_refresh})
    access_token, new_refresh = token_data.get("access_token"), token_data.get("refresh_token")
    if not access_token or not new_refresh:
        raise RuntimeError("Strava token refresh response was missing required tokens")

    # Persist replacement before any subsequent API request or public output write.
    _persist_rotated_token(new_refresh, encryption_key)
    activities = _validate_activities(_get_json(ACTIVITIES_URL + "?per_page=5&page=1", access_token))
    map_url = _update_map(activities[0])
    rendered = render_activity_json(activities, map_url)
    if any(secret in rendered for secret in (access_token, new_refresh, client_secret)):
        raise RuntimeError("Refusing to write activity output containing credential material")
    _atomic_write(ACTIVITIES_PATH, rendered)
    _atomic_write(MAP_URL_PATH, map_url + "\n")
    print(f"Updated {len(activities)} activities; rotated token persisted encrypted.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(refresh())
    except (KeyError, RuntimeError, ValueError) as error:
        print(f"Strava refresh failed: {error}", file=sys.stderr)
        raise SystemExit(1)
