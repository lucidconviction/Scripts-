"""
MegaSource scraper: Dailymotion
===============================
Protocol:
    TITLE, VERSION, DESCRIPTION
    get_streams(media_type: str, media_id: str, config: dict | None) -> list[dict]

Fetches trending videos from Dailymotion's public API and resolves direct
stream URLs from the player metadata endpoint. Standard library only.

Config options:
    limit (int, default 50): max number of streams to return
    sort (str, default "visited"): sort order ("visited", "trending", "recent")
"""

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

TITLE = "Dailymotion"
VERSION = "1.0.0"
DESCRIPTION = "Trending videos from dailymotion.com"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
BASE_URL = "https://www.dailymotion.com"


def _fetch(url, timeout=20, retries=3, accept="application/json"):
    headers = {"User-Agent": USER_AGENT, "Accept": accept}
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            return exc.read().decode("utf-8", errors="replace")
        except Exception:
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
    return ""


DEFAULT_CHANNELS = [
    ("News", "news"),
    ("Sports", "sport"),
    ("Entertainment", "fun"),
    ("Music", "music"),
    ("Movies", "shortfilms"),
    ("Tech", "tech"),
    ("Travel", "travel"),
    ("Gaming", "videogames"),
]


def _resolve_video(video_id):
    meta = _fetch(f"{BASE_URL}/player/metadata/video/{video_id}")
    if not meta:
        return None
    try:
        data = json.loads(meta)
    except (ValueError, TypeError):
        return None

    qualities = data.get("qualities") or {}
    auto = qualities.get("auto") or []
    if auto and auto[0].get("url"):
        return auto[0]["url"]
    return None


def _scrape(limit, channels):
    streams = []
    seen = set()

    for channel_name, channel_id in channels:
        params = urllib.parse.urlencode(
            {
                "channel": channel_id,
                "sort": "trending",
                "limit": min(limit, 100),
                "fields": "id,title",
            }
        )
        body = _fetch(f"https://api.dailymotion.com/videos?{params}")
        if not body:
            continue
        try:
            data = json.loads(body)
        except (ValueError, TypeError):
            continue

        for item in data.get("list") or []:
            video_id = item.get("id")
            title = item.get("title")
            if not video_id or not title:
                continue
            url = _resolve_video(video_id)
            if not url:
                continue
            streams.append(
                {
                    "name": f"r/{channel_name}",
                    "title": title,
                    "url": url,
                    "behaviorHints": {
                        "notMyMetadata": True,
                        "proxyHeaders": {
                            "request": {
                                "User-Agent": USER_AGENT,
                                "Referer": BASE_URL + "/",
                            }
                        },
                    },
                }
            )
            if len(streams) >= limit:
                return streams

    return streams


def get_streams(media_type, media_id, config=None):
    limit = 50
    channels = DEFAULT_CHANNELS
    if isinstance(config, dict):
        try:
            limit = int(config.get("limit", limit))
        except (TypeError, ValueError):
            pass
        configured_channels = config.get("channels")
        if isinstance(configured_channels, list) and configured_channels:
            channels = [
                (name, cid) for name, cid in configured_channels
                if isinstance(name, str) and isinstance(cid, str)
            ] or DEFAULT_CHANNELS
    return _scrape(limit, channels)
