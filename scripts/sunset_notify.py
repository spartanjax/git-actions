#!/usr/bin/env python3
"""Push today's Mt Eden sunset and tomorrow's sunrise as an ntfy notification.

Coordinates are for Maungawhau / Mount Eden, Auckland, New Zealand.
Sunrise/sunset times come from https://api.sunrise-sunset.org and are
converted to Auckland local time (DST-aware) before being sent.
"""

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

LAT = -36.877
LNG = 174.764
TZ = ZoneInfo("Pacific/Auckland")

API_URL = "https://api.sunrise-sunset.org/json"
NTFY_BASE = "https://ntfy.sh"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "mt-eden-sunsets")
NTFY_TITLE = "Maungawhau ☀️ Sun Times"
USER_AGENT = "mt-eden-sun-times/1.0 (+https://github.com)"


def fetch_sun_times(date: str) -> dict:
    """Fetch sunrise/sunset data for a given YYYY-MM-DD date."""
    params = urllib.parse.urlencode(
        {"lat": LAT, "lng": LNG, "date": date, "formatted": 0}
    )
    req = urllib.request.Request(
        f"{API_URL}?{params}", headers={"User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    if data.get("status") != "OK":
        raise RuntimeError(f"Unexpected API response: {data}")
    return data["results"]


def to_auckland(iso_timestamp: str) -> datetime:
    """Convert an ISO 8601 UTC timestamp to Auckland local time."""
    return datetime.fromisoformat(iso_timestamp).astimezone(TZ)


def pretty(dt: datetime) -> str:
    """Format a datetime as e.g. 7:34pm (no leading zero, lowercase)."""
    text = dt.strftime("%I:%M%p").lower()
    return text[1:] if text.startswith("0") else text


def main() -> None:
    now = datetime.now(TZ)
    force = os.environ.get("FORCE_RUN") == "1"

    # Only the cron entry matching Auckland's 5pm should send. The other
    # (DST) entry lands on 4pm or 6pm and stays quiet. Manual runs can force.
    if not force and now.hour != 17:
        print(f"Skipping: Auckland time is {now:%H:%M}, not 5pm.")
        return

    today = now.strftime("%Y-%m-%d")
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")

    sunset = to_auckland(fetch_sun_times(today)["sunset"])
    sunrise = to_auckland(fetch_sun_times(tomorrow)["sunrise"])

    message = f"🌅 Sunset today: {pretty(sunset)} · 🌄 Sunrise tomorrow: {pretty(sunrise)}"

    payload = json.dumps(
        {
            "topic": NTFY_TOPIC,
            "title": NTFY_TITLE,
            "message": message,
            "tags": ["sunny"],
        },
        ensure_ascii=False,
    ).encode("utf-8")

    req = urllib.request.Request(
        NTFY_BASE,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        print(f"Sent (HTTP {resp.status}): {message}")


if __name__ == "__main__":
    main()
