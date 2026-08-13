"""
MegaSource scraper: Worldstar Hip Hop
=====================================
Protocol:
    TITLE, VERSION, DESCRIPTION
    get_streams(media_type: str, media_id: str, config: dict | None) -> list[dict]

Scrapes https://worldstarhiphop.com/videos/ for the latest clips by parsing the
Next.js embedded JSON (__NEXT_DATA__ / __next_f) and falling back to direct
.mp4 URLs. Standard library only.

Config options:
    limit (int, default 50): max number of streams to return
"""

import html
import json
import re
import time
import urllib.error
import urllib.request

TITLE = "Worldstar Hip Hop"
VERSION = "1.0.0"
DESCRIPTION = "Latest videos from worldstarhiphop.com"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
BASE_URL = "https://worldstarhiphop.com"


def _fetch(url, timeout=15):
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


def _extract_videos(text):
    results = []
    seen = set()
    pos = 0
    while pos < len(text):
        t_idx = text.find('"title"', pos)
        if t_idx == -1:
            break
        val_start = text.find('"', t_idx + 7)
        if val_start == -1:
            break
        val_end = val_start + 1
        while val_end < len(text):
            if text[val_end] == '"' and text[val_end - 1] != "\\":
                break
            val_end += 1
        title = text[val_start + 1:val_end]

        u_idx = text.find('"utLocation"', val_end)
        if u_idx == -1 or u_idx - val_end > 2000:
            url_start = text.find("mp4", val_end)
            if url_start != -1 and url_start - val_end < 3000:
                u_val_end = url_start + 4
                while u_val_end < len(text):
                    if text[u_val_end] == '"' and text[u_val_end - 1] != "\\":
                        break
                    u_val_end += 1
                url = text[url_start:u_val_end].split("?")[0].split("#")[0]
                if url.endswith(".mp4") and url not in seen:
                    seen.add(url)
                    results.append((title.replace('\\"', '"'), url))
            pos = val_end + 1
            continue

        u_val_start = text.find('"', u_idx + 13)
        if u_val_start == -1:
            break
        u_val_end = u_val_start + 1
        while u_val_end < len(text):
            if text[u_val_end] == '"' and text[u_val_end - 1] != "\\":
                break
            u_val_end += 1
        url = text[u_val_start + 1:u_val_end]

        if url.endswith(".mp4") and url not in seen:
            seen.add(url)
            results.append((title.replace('\\"', '"'), url))

        pos = val_end + 1
    return results


def _page_videos(page):
    page_url = (
        BASE_URL + "/videos/"
        if page == 1
        else f"{BASE_URL}/videos/page/{page}/"
    )
    content = _fetch(page_url)
    if not content:
        return []

    json_data = ""
    next_data = re.search(
        r'<script id="__NEXT_DATA__"[^>]*type="application/json"[^>]*>'
        r'(\{[\s\S]*?\})</script>',
        content,
    )
    if next_data:
        json_data = next_data.group(1)
    else:
        flight = re.findall(
            r'<script[^>]*>self\.__next_f_push\(\[1,"([\s\S]*?)"\]\)</script>',
            content,
        )
        for chunk in flight:
            json_data += (
                chunk.replace('\\"', '"')
                .replace("\\n", "\n")
                .replace("\\\\", "\\")
            )

    if json_data:
        return _extract_videos(json_data)

    fallback = re.sub(r"<[^>]+>", " ", content)
    urls = re.findall(r"(https?://[^\s\"']+\.mp4)", fallback, re.I)
    return [("Worldstar Video", u) for u in urls]


def _scrape(limit):
    all_videos = {}
    for page in range(1, 6):
        for title, url in _page_videos(page):
            if url not in all_videos:
                all_videos[url] = html.unescape(title) or "Worldstar Video"
        if len(all_videos) >= limit:
            break

    streams = []
    for url, title in list(all_videos.items())[:limit]:
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
                            "Referer": BASE_URL + "/videos/",
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
