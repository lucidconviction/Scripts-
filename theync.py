"""
MegaSource scraper: TheYNC
==========================
Protocol:
    TITLE, VERSION, DESCRIPTION
    get_streams(media_type: str, media_id: str, config: dict | None) -> list[dict]

Scrapes https://theync.com/latest-updates/ for the latest videos and resolves
direct /get_file/ URLs. Standard library only.

Config options:
    limit (int, default 50): max number of streams to return
"""

import html
import re
import time
import urllib.error
import urllib.request

TITLE = "TheYNC"
VERSION = "1.0.0"
DESCRIPTION = "Latest videos from theync.com"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
BASE_URL = "https://theync.com"


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
    page = _fetch(BASE_URL + "/latest-updates/")
    if not page:
        return []

    resolved = {}

    for match in re.finditer(
        r"https://theync\.com/get_file/\d+/[^\"'\s]+", page, re.I
    ):
        url = match.group(0)
        if url not in resolved:
            pos = page.find(url)
            nearby = page[max(0, pos - 500):pos]
            title_match = re.search(r'alt="([^"]+)"', nearby, re.I)
            title = html.unescape(title_match.group(1)).strip() if title_match else "TheYNC Video"
            resolved[url] = title

    video_urls = list(
        dict.fromkeys(
            re.findall(r'href="(https://theync\.com/video/\d+[^"]*)"', page, re.I)
        )
    )

    for video_url in video_urls:
        if len(resolved) >= limit:
            break
        video_page = _fetch(video_url.split("#")[0])
        if not video_page:
            continue
        get_file = re.search(
            r"https://theync\.com/get_file/\d+/[^\"'\s]+", video_page, re.I
        )
        if get_file and get_file.group(0) not in resolved:
            title_match = re.search(r"<title>([^<]*)</title>", video_page, re.I)
            title = (
                html.unescape(title_match.group(1)).replace("— TheYNC", "").strip()
                if title_match
                else "TheYNC Video"
            )
            resolved[get_file.group(0)] = title

    streams = []
    for url, title in list(resolved.items())[:limit]:
        streams.append(
            {
                "name": TITLE,
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
    return streams


def get_streams(media_type, media_id, config=None):
    limit = 50
    if isinstance(config, dict):
        try:
            limit = int(config.get("limit", limit))
        except (TypeError, ValueError):
            pass
    return _scrape(limit)
