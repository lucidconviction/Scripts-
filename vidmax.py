"""
MegaSource scraper: Vidmax
===========================
Protocol:
    TITLE, VERSION, DESCRIPTION
    get_streams(media_type: str, media_id: str, config: dict | None) -> list[dict]

Scrapes https://vidmax.com/ for the latest videos and resolves direct .mp4
URLs from each video page. Standard library only.

Config options:
    limit (int, default 50): max number of streams to return
"""

import html
import re
import time
import urllib.error
import urllib.request

TITLE = "Vidmax"
VERSION = "1.0.0"
DESCRIPTION = "Latest videos from vidmax.com"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
BASE_URL = "https://vidmax.com"


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


def _extract_listing(html_text):
    videos = []
    seen = set()
    pattern = re.compile(
        r'href="((?:https://vidmax\.com)?/video/\d+[^"\']*?)"', re.I
    )
    for match in pattern.finditer(html_text):
        url = match.group(1)
        if url.startswith("http"):
            url = url.split("?")[0]
        else:
            url = BASE_URL + url.split("?")[0]

        title = "Vidmax Video"
        window = html_text[max(0, match.start() - 200): match.start() + 200]
        title_in = re.search(r'<img[^>]*alt="([^"]+)"', window, re.I)
        if title_in:
            title = html.unescape(title_in.group(1)).strip()

        if url not in seen:
            seen.add(url)
            videos.append((title or "Vidmax Video", url))
    return videos


def _resolve_video_url(video_url):
    page = _fetch(video_url)
    if not page:
        return None

    patterns = [
        r'<source[^>]*src=["\']([^"\']+\.(?:mp4|webm))["\']',
        r'<video[^>]*src=["\']([^"\']+\.(?:mp4|webm))["\']',
        r'data-src=["\']([^"\']+\.(?:mp4|webm))["\']',
        r'<iframe[^>]*src=["\']([^"\']+)["\']',
        r'src=["\']([^"\']+\.(?:mp4|webm))["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, page, re.I)
        if match:
            src = match.group(1)
            if "<iframe" in pattern or "iframe" in pattern:
                iframe_url = src if src.startswith("http") else BASE_URL + src
                inner = _fetch(iframe_url)
                if inner:
                    inner_match = re.search(
                        r'src=["\']([^"\']+\.(?:mp4|webm))["\']', inner, re.I
                    )
                    if inner_match:
                        return inner_match.group(1).split("?")[0]
            else:
                return src.split("?")[0]
    return None


def _scrape(limit):
    videos = []
    for page_num in range(1, 16):
        page_url = BASE_URL if page_num == 1 else f"{BASE_URL}/page{page_num}.html"
        page = _fetch(page_url)
        if not page:
            continue
        videos.extend(_extract_listing(page))
        if len(videos) >= limit:
            break
    videos = videos[:limit]

    streams = []
    for title, video_url in videos:
        mp4 = _resolve_video_url(video_url)
        if mp4:
            streams.append(
                {
                    "name": TITLE,
                    "title": title,
                    "url": mp4,
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
    return streams


def get_streams(media_type, media_id, config=None):
    limit = 50
    if isinstance(config, dict):
        try:
            limit = int(config.get("limit", limit))
        except (TypeError, ValueError):
            pass
    return _scrape(limit)
