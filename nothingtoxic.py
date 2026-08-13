"""
MegaSource scraper: NothingToxic
================================
Protocol:
    TITLE, VERSION, DESCRIPTION
    get_streams(media_type: str, media_id: str, config: dict | None) -> list[dict]

Scrapes https://nothingtoxic.com/ for the latest "out" links and resolves
direct .mp4/.m3u8 URLs from each page. Standard library only.

Config options:
    limit (int, default 50): max number of streams to return
"""

import html
import re
import time
import urllib.error
import urllib.request

TITLE = "NothingToxic"
VERSION = "1.0.0"
DESCRIPTION = "Latest videos from nothingtoxic.com"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
BASE_URL = "https://nothingtoxic.com"


def _fetch(url, timeout=15, retries=3):
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html",
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


def _scrape(limit):
    page = _fetch(BASE_URL + "/")
    if not page:
        return []

    video_links = list(
        dict.fromkeys(
            re.findall(r'href="(https://nothingtoxic\.com/out/\d+[^"]*)"', page, re.I)
        )
    )[:limit]

    streams = []
    for link in video_links:
        video_page = _fetch(link)
        if not video_page:
            continue

        src_match = re.search(
            r'src="([^"]+\.(mp4|m3u8)[^"]*)"|data-src="([^"]+\.(mp4|m3u8)[^"]*)"',
            video_page,
            re.I,
        )
        video_url = src_match.group(1) or src_match.group(3) if src_match else None
        if not video_url:
            continue

        title_match = re.search(r"<title>([^<]*)</title>", video_page, re.I)
        title = (
            html.unescape(title_match.group(1)).strip()
            if title_match
            else "Untitled"
        )

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
