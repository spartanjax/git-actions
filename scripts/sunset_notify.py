#!/usr/bin/env python3
"""Push today's Mt Eden sunset, with expected weather, as an ntfy notification.

Coordinates are for Maungawhau / Mount Eden, Auckland, New Zealand.
The sunset time comes from https://api.sunrise-sunset.org and is converted to
Auckland local time (DST-aware). Expected conditions around sunset come from
the Open-Meteo public forecast API (https://open-meteo.com).
"""

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

LAT = -36.877
LNG = 174.764
TZ = ZoneInfo("Pacific/Auckland")

API_URL = "https://api.sunrise-sunset.org/json"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
NTFY_BASE = "https://ntfy.sh"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "mt-eden-sunsets")
SUNSET_EMOJI = "🌇"
NEUTRAL_EMOJI = "🌥️"
USER_AGENT = "mt-eden-sun-times/1.0 (+https://github.com)"

# WMO weather interpretation codes -> (emoji, short description).
# https://open-meteo.com/en/docs#weathervariables
WEATHER_CODES = {
    0: ("☀️", "clear sky"),
    1: ("🌤️", "mainly clear"),
    2: ("⛅", "partly cloudy"),
    3: ("☁️", "overcast"),
    45: ("🌫️", "fog"),
    48: ("🌫️", "freezing fog"),
    51: ("🌦️", "light drizzle"),
    53: ("🌦️", "drizzle"),
    55: ("🌦️", "dense drizzle"),
    56: ("🌧️", "freezing drizzle"),
    57: ("🌧️", "dense freezing drizzle"),
    61: ("🌧️", "light rain"),
    63: ("🌧️", "rain"),
    65: ("🌧️", "heavy rain"),
    66: ("🌧️", "freezing rain"),
    67: ("🌧️", "heavy freezing rain"),
    71: ("🌨️", "light snow"),
    73: ("🌨️", "snow"),
    75: ("❄️", "heavy snow"),
    77: ("❄️", "snow grains"),
    80: ("🌦️", "light rain showers"),
    81: ("🌧️", "rain showers"),
    82: ("⛈️", "violent rain showers"),
    85: ("🌨️", "snow showers"),
    86: ("❄️", "heavy snow showers"),
    95: ("⛈️", "thunderstorm"),
    96: ("⛈️", "thunderstorm with hail"),
    99: ("⛈️", "thunderstorm with heavy hail"),
}


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


def fetch_weather(date: str, sunset: datetime) -> dict:
    """Return the forecast at the hour nearest sunset as a dict."""
    params = urllib.parse.urlencode(
        {
            "latitude": LAT,
            "longitude": LNG,
            "hourly": (
                "temperature_2m,apparent_temperature,weather_code,"
                "precipitation_probability,"
                "cloud_cover_low,cloud_cover_mid,cloud_cover_high"
            ),
            "timezone": str(TZ),
            "start_date": date,
            "end_date": date,
        }
    )
    req = urllib.request.Request(
        f"{WEATHER_URL}?{params}", headers={"User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)

    hourly = data.get("hourly", {})
    times = hourly.get("time") or []
    if not times:
        raise RuntimeError(f"Unexpected weather response: {data}")

    # Open-Meteo returns local ISO timestamps (without offset); attach our zone.
    best = min(
        range(len(times)),
        key=lambda i: abs(
            datetime.fromisoformat(times[i]).replace(tzinfo=TZ) - sunset
        ),
    )

    def at(key: str):
        return (hourly.get(key) or [])[best]

    return {
        "temperature": at("temperature_2m"),
        "apparent": at("apparent_temperature"),
        "weather_code": at("weather_code"),
        "precip_probability": at("precipitation_probability"),
        "cloud_low": at("cloud_cover_low"),
        "cloud_mid": at("cloud_cover_mid"),
        "cloud_high": at("cloud_cover_high"),
    }


def sunset_outlook(low: int, mid: int, high: int) -> str:
    """Short verdict on how colourful tonight's sunset is likely to be.

    Low cloud near the horizon blocks the sun; broken mid/high cloud overhead
    is what catches the light and produces colour.
    """
    upper = max(mid, high)
    if low >= 70:
        return "poor — thick low cloud likely hides the sun"
    if low >= 40:
        return "mixed — some low cloud may block the horizon"
    if upper >= 70:
        return "muted — heavy cloud overhead, little colour"
    if upper >= 20:
        return "promising — broken cloud should catch the light"
    return "clear — a simple, clean sunset"


def cloud_score(low: int, mid: int, high: int) -> int:
    """Single 0-100 rating of how good the sunset is likely to be.

    A clear horizon (little low cloud) matters most; broken mid/high cloud
    overhead is what catches the light, so it peaks around 40% cover.
    """
    horizon = 100 - low
    upper = max(mid, high)
    colour = max(0.0, 100 - abs(upper - 40) * 100 / 60)
    return round(0.6 * horizon + 0.4 * colour)


def weather_tag(code: int) -> str:
    """Map a WMO weather code to an ntfy tag category."""
    if code in (0, 1):
        return "sunny"
    if code in (2, 3):
        return "cloudy"
    if code in (45, 48):
        return "fog"
    if 51 <= code <= 67 or 80 <= code <= 82:
        return "rain"
    if 71 <= code <= 77 or 85 <= code <= 86:
        return "snow"
    if code >= 95:
        return "storm"
    return "sunny"


def to_auckland(iso_timestamp: str) -> datetime:
    """Convert an ISO 8601 UTC timestamp to Auckland local time."""
    return datetime.fromisoformat(iso_timestamp).astimezone(TZ)


def pretty(dt: datetime) -> str:
    """Format a datetime as e.g. 7:34pm (no leading zero, lowercase)."""
    text = dt.strftime("%I:%M%p").lower()
    return text[1:] if text.startswith("0") else text


def main() -> None:
    now = datetime.now(TZ)
    today = now.strftime("%Y-%m-%d")

    sunset = to_auckland(fetch_sun_times(today)["sunset"])

    try:
        w = fetch_weather(today, sunset)
        emoji, description = WEATHER_CODES.get(
            w["weather_code"], (NEUTRAL_EMOJI, "mixed conditions")
        )
        message = "\n".join(
            [
                f"{round(w['temperature'])}°C "
                f"(feels {round(w['apparent'])}°C) and {description} {emoji}",
                f"{round(w['precip_probability'])}% chance of rain · "
                f"cloud score {cloud_score(w['cloud_low'], w['cloud_mid'], w['cloud_high'])}/100",
                f"{sunset_outlook(w['cloud_low'], w['cloud_mid'], w['cloud_high'])}",
            ]
        )
        tag = weather_tag(w["weather_code"])
    except Exception:
        message = f"Expected weather unavailable for sunset {NEUTRAL_EMOJI}"
        tag = "sunset"

    title = f"{SUNSET_EMOJI} Sunset at {pretty(sunset)}"

    payload = json.dumps(
        {
            "topic": NTFY_TOPIC,
            "title": title,
            "message": message,
            "tags": [tag],
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
        print(f"Sent (HTTP {resp.status}): {title} — {message}")


if __name__ == "__main__":
    main()
