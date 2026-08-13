"""
MegaSource scraper: Kaotic
==========================
Protocol:
    TITLE, VERSION, DESCRIPTION
    get_streams(media_type: str, media_id: str, config: dict | None) -> list[dict]

Scrapes https://kaotic.com/recent/ for the latest video posts and resolves
direct .mp4/.webm URLs from each post page. Standard library only.

Config options:
    limit (int, default 50): max number of streams to return
"""

import html
import re
import time
import urllib.error
import urllib.request

TITLE = "Kaotic"
VERSION = "1.0.0"
DESCRIPTION = "Latest videos from kaotic.com"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
BASE_URL = "https://kaotic.com"


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
    page = _fetch(BASE_URL + "/recent/")
    if not page:
        return []

    post_urls = list(
        dict.fromkeys(
            re.findall(r'href="(https://kaotic\.com/video/[\w]+)"', page, re.I)
        )
    )[:limit]

    resolved = []
    batch_size = 10
    for i in range(0, len(post_urls), batch_size):
        batch = post_urls[i:i + batch_size]
        for post_url in batch:
            post_page = _fetch(post_url)
            if not post_page:
                continue
            src_match = re.search(r'src="([^"]+\.(mp4|webm))"', post_page, re.I)
            if not src_match:
                continue
            title_match = re.search(r"<title>([^<]*)</title>", post_page, re.I)
            title = (
                html.unescape(title_match.group(1)).strip()
                if title_match
                else "Untitled"
            )
            resolved.append(
                {
                    "name": TITLE,
                    "title": title,
                    "url": src_match.group(1),
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
            if len(resolved) >= limit:
                break
        if len(resolved) >= limit:
            break

    return resolved


def get_streams(media_type, media_id, config=None):
    limit = 50
    if isinstance(config, dict):
        try:
            limit = int(config.get("limit", limit))
        except (TypeError, ValueError):
            pass
    return _scrape(limit)
