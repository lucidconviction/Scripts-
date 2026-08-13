"""
MegaSource scraper: DailyCommercials
====================================
Protocol:
    TITLE, VERSION, DESCRIPTION
    get_streams(media_type: str, media_id: str, config: dict | None) -> list[dict]

Scrapes the dailycommercials.com RSS feed for direct wordpress.com .mp4
URLs. Standard library only.

Config options:
    limit (int, default 50): max number of streams to return
"""

import html
import re
import time
import urllib.error
import urllib.request

TITLE = "DailyCommercials"
VERSION = "1.0.0"
DESCRIPTION = "Latest videos from dailycommercials.com"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
BASE_URL = "https://dailycommercials.com"


def _fetch(url, timeout=20, retries=3):
    headers = {"User-Agent": USER_AGENT, "Accept": "application/rss+xml"}
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


def _scrape(limit):
    streams = []
    seen = set()

    for page_num in range(1, 6):
        feed_url = (
            BASE_URL + "/feed/"
            if page_num == 1
            else f"{BASE_URL}/feed/?paged={page_num}"
        )
        xml = _fetch(feed_url)
        if not xml:
            continue

        items = xml.split("<item>")[1:]
        for item in items:
            title_match = re.search(
                r"<title>(?:<!\[CDATA\[)?([^\]]*)(?:\]\]>)?</title>", item
            )
            mp4_match = re.search(
                r"(https://videos\.files\.wordpress\.com/[^\"'<>\s]+\.mp4)", item
            )
            if not (title_match and mp4_match):
                continue
            title = (
                title_match.group(1).replace("<![CDATA[", "").replace("]]>", "").strip()
            )
            url = mp4_match.group(1)
            if (
                url in seen
                or not title
                or title.lower() in ("daily commercials", "dailey commercials")
            ):
                continue
            seen.add(url)
            streams.append(
                {
                    "name": TITLE,
                    "title": html.unescape(title),
                    "url": url,
                    "behaviorHints": {
                        "notMyMetadata": True,
                        "proxyHeaders": {
                            "request": {"User-Agent": USER_AGENT, "Referer": BASE_URL + "/"}
                        },
                    },
                }
            )
            if len(streams) >= limit:
                return streams

    return streams


def get_streams(media_type, media_id, config=None):
    limit = 50
    if isinstance(config, dict):
        try:
            limit = int(config.get("limit", limit))
        except (TypeError, ValueError):
            pass
    return _scrape(limit)
