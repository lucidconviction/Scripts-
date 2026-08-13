"""
MegaSource scraper: YouTube (via RSS + Piped/Invidious)
=======================================================
Protocol:
    TITLE, VERSION, DESCRIPTION
    get_streams(media_type: str, media_id: str, config: dict | None) -> list[dict]

Fetches the latest uploads from a set of channels using YouTube's public
RSS feed (no API key) and resolves direct stream URLs through the Piped
API (falls back to Invidious). No yt-dlp required.

Standard library only.

Config options:
    limit (int, default 15): max number of streams to return
    channels (list, default): list of channel URLs (@handle, UC-id, /channel/) to scrape
"""

import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

TITLE = "YouTube"
VERSION = "1.0.0"
DESCRIPTION = "Latest uploads from channels (via RSS + Piped/Invidious)"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

PIPED_INSTANCES = [
    "https://api.piped.private.coffee",
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.leptons.xyz",
    "https://pipedapi.adminforge.de",
    "https://pipedapi.ducks.party",
    "https://pipedapi.moomoo.me",
    "https://pipedapi.drgns.space",
    "https://pipedapi.cai-chan.me",
]

INVIDIOUS_INSTANCES = [
    "https://yewtu.be",
    "https://inv.nadeko.net",
    "https://invidious.nerdvpn.de",
    "https://iv.melmac.space",
]


def _parse_quality(value):
    try:
        return int(re.sub(r"\D", "", str(value)) or 0)
    except (TypeError, ValueError):
        return 0

DEFAULT_CHANNELS = [
    "https://www.youtube.com/@PiersMorganUncensored",
    "https://www.youtube.com/@TheDailyShow",
    "https://www.youtube.com/@espn",
    "https://www.youtube.com/@ufc",
]


def _fetch(url, timeout=20, retries=2):
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception:
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
    return ""


def _channel_id(channel_url):
    """Resolve a channel URL (@handle or /channel/UC...) to a UC- id."""
    if "/channel/" in channel_url:
        match = re.search(r"/channel/(UC[\w-]+)", channel_url)
        if match:
            return match.group(1)

    page = _fetch(channel_url, timeout=20)
    match = re.search(r'"channelId"\s*:\s*"(UC[\w-]{22})"', page)
    if match:
        return match.group(1)
    return None


def _channel_uploads(channel_id):
    """Latest uploads via YouTube RSS feed. Returns list of (video_id, title)."""
    rss = _fetch(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}")
    if not rss:
        return []
    entries = re.findall(r"<entry>.*?</entry>", rss, re.S)
    results = []
    for entry in entries:
        vid = re.search(r"<yt:videoId>(.*?)</yt:videoId>", entry)
        title = re.search(r"<title>(.*?)</title>", entry, re.S)
        if vid and title:
            results.append(
                (vid.group(1), html.unescape(title.group(1)).strip())
            )
    return results


def _resolve_stream(video_id, budget=20):
    import time as _time
    start = _time.time()

    def remaining():
        return max(1, budget - (_time.time() - start))

    for base in PIPED_INSTANCES:
        if _time.time() - start >= budget:
            break
        body = _fetch(f"{base}/streams/{video_id}", timeout=min(8, remaining()), retries=1)
        if not body or not body.startswith("{"):
            continue
        try:
            data = json.loads(body)
        except (ValueError, TypeError):
            continue
        video_streams = data.get("videoStreams") or []
        video_streams.sort(key=lambda s: _parse_quality(s.get("quality")), reverse=True)
        for s in video_streams:
            url = s.get("url", "")
            if url.startswith("http") and "m3u8" not in url:
                if not s.get("videoOnly"):
                    return url
        for s in video_streams:
            url = s.get("url", "")
            if url.startswith("http") and "m3u8" not in url:
                return url
        if video_streams and video_streams[0].get("url"):
            return video_streams[0]["url"]
        for a in data.get("audioStreams") or []:
            url = a.get("url", "")
            if url.startswith("http"):
                return url

    for base in INVIDIOUS_INSTANCES:
        if _time.time() - start >= budget:
            break
        body = _fetch(f"{base}/api/v1/videos/{video_id}", timeout=min(8, remaining()), retries=1)
        if not body or not body.startswith("{"):
            continue
        try:
            data = json.loads(body)
        except (ValueError, TypeError):
            continue
        formats = data.get("formatStreams") or []
        formats.sort(
            key=lambda f: _parse_quality(f.get("qualityLabel")), reverse=True
        )
        for s in formats:
            url = s.get("url", "")
            if url.startswith("http"):
                return url
        video_streams = [
            f for f in data.get("adaptiveFormats") or []
            if (f.get("type") or "").startswith("video")
        ]
        video_streams.sort(
            key=lambda f: _parse_quality(f.get("qualityLabel")), reverse=True
        )
        if video_streams and video_streams[0].get("url"):
            return video_streams[0]["url"]

    return None


def _scrape(limit, channels):
    streams = []
    seen = set()
    import time as _time
    deadline = _time.time() + 60
    for channel_url in channels:
        if _time.time() >= deadline:
            break
        channel_id = _channel_id(channel_url)
        if not channel_id:
            continue
        for video_id, title in _channel_uploads(channel_id):
            if video_id in seen:
                continue
            seen.add(video_id)
            if _time.time() >= deadline:
                return streams
            stream_url = _resolve_stream(video_id, budget=min(15, max(5, deadline - _time.time())))
            if not stream_url:
                continue
            streams.append(
                {
                    "name": TITLE,
                    "title": title,
                    "url": stream_url,
                    "behaviorHints": {"notMyMetadata": True},
                }
            )
            if len(streams) >= limit:
                return streams
        if len(streams) >= limit:
            break
    return streams


def get_streams(media_type, media_id, config=None):
    limit = 15
    channels = DEFAULT_CHANNELS
    if isinstance(config, dict):
        try:
            limit = int(config.get("limit", limit))
        except (TypeError, ValueError):
            pass
        configured_channels = config.get("channels")
        if isinstance(configured_channels, list) and configured_channels:
            channels = configured_channels
    return _scrape(limit, channels)
