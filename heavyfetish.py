"""
MegaSource scraper: HeavyFetish
===============================
Protocol:
    TITLE, VERSION, DESCRIPTION
    get_streams(media_type: str, media_id: str, config: dict | None) -> list[dict]

Scrapes the https://heavyfetish.com/rss/ feed and resolves direct video URLs
from each video page. Standard library only.

Config options:
    limit (int, default 50): max number of streams to return
"""

import html
import re
import time
import urllib.error
import urllib.request

TITLE = "HeavyFetish"
VERSION = "1.0.0"
DESCRIPTION = "Latest videos from heavyfetish.com"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
BASE_URL = "https://heavyfetish.com"


def _fetch(url, timeout=15, retries=3):
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Referer": BASE_URL + "/",
    }
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


def _resolve_video_url(page_url):
    page = _fetch(page_url)
    if not page:
        return None

    url_match = re.search(r"video_url\s*:\s*'([^']+)'", page)
    if not url_match:
        return None

    video_url = url_match.group(1)
    if not video_url.startswith("http"):
        video_url = BASE_URL + video_url

    title_match = re.search(r"video_title\s*:\s*'([^']+)'", page)
    title = html.unescape(title_match.group(1)).strip() if title_match else "Untitled"

    return title, video_url


def _scrape(limit):
    rss = _fetch(BASE_URL + "/rss/")
    if not rss:
        return []

    video_links = []
    for match in re.finditer(r"<link>([^<]+)</link>", rss):
        link = match.group(1).strip()
        if "/videos/" in link and link not in video_links:
            video_links.append(link)

    streams = []
    for link in video_links[:limit]:
        result = _resolve_video_url(link)
        if not result:
            continue
        title, video_url = result
        streams.append(
            {
                "name": TITLE,
                "title": title,
                "url": video_url,
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
            break

    return streams


def get_streams(media_type, media_id, config=None):
    limit = 50
    if isinstance(config, dict):
        try:
            limit = int(config.get("limit", limit))
        except (TypeError, ValueError):
            pass
    return _scrape(limit)
