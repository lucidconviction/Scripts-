"""
MegaSource scraper: HeavyR
==========================
Protocol:
    TITLE, VERSION, DESCRIPTION
    get_streams(media_type: str, media_id: str, config: dict | None) -> list[dict]

Scrapes https://www.heavy-r.com/ for the latest video links and resolves
direct .mp4/.webm URLs from each video page. Standard library only.

Config options:
    limit (int, default 50): max number of streams to return
"""

import html
import re
import time
import urllib.error
import urllib.request

TITLE = "HeavyR"
VERSION = "1.0.0"
DESCRIPTION = "Latest videos from heavy-r.com"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
BASE_URL = "https://www.heavy-r.com"


def _fetch(url, timeout=20, retries=3):
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

    video_urls = []
    for match in re.finditer(r'href="(/?video/\d+[^"]*)"', page, re.I):
        path = match.group(1)
        if not path.startswith("/"):
            path = "/" + path
        url = BASE_URL + path.split("?")[0]
        if url not in video_urls:
            video_urls.append(url)

    streams = []
    for video_url in video_urls[:limit]:
        video_page = _fetch(video_url)
        if not video_page:
            continue

        src_match = re.search(r'src="([^"]+\.(mp4|webm))"', video_page, re.I)
        if not src_match:
            data_src = re.search(r'data-src="([^"]+\.(mp4|webm))"', video_page, re.I)
            if not data_src:
                continue
            src = data_src.group(1)
            title = "HeavyR Video"
        else:
            src = src_match.group(1)
            title_match = re.search(r"<title>([^<]*)</title>", video_page, re.I)
            title = (
                html.unescape(title_match.group(1))
                .replace(" - Heavy-R.com", "")
                .replace(" - Free Porn Videos", "")
                .strip()
                if title_match
                else "HeavyR Video"
            )

        full_url = src if src.startswith("http") else BASE_URL + src
        streams.append(
            {
                "name": TITLE,
                "title": title,
                "url": full_url,
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
