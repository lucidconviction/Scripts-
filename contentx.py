"""
MegaSource scraper: ContentX
============================
Protocol:
    TITLE, VERSION, DESCRIPTION
    get_streams(media_type: str, media_id: str, config: dict | None) -> list[dict]

Resolves a file page on contentx.me to a direct stream URL.

Pass the file URL as media_id. Standard library only.
"""

import re
import time
import urllib.error
import urllib.parse
import urllib.request

TITLE = "ContentX"
VERSION = "1.0.0"
DESCRIPTION = "Resolve contentx.me links"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
MAIN_URL = "https://contentx.me"


def _fetch(url, timeout=20, retries=3, headers=None, referer=None):
    h = {
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }
    if referer:
        h["Referer"] = referer
    if headers:
        h.update(headers)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            return exc.read().decode("utf-8", errors="replace")
        except Exception:
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
    return ""


def _resolve(url):
    page = _fetch(url)
    if not page:
        return None

    extract_match = re.search(r"window\.openPlayer\('([^']+)'", page)
    if not extract_match:
        return None

    source_url = f"{MAIN_URL}/source2.php?v={extract_match.group(1)}"
    source_body = _fetch(source_url, referer=url)
    if not source_body:
        return None

    file_match = re.search(r'"file":"([^"]+)"', source_body)
    if not file_match:
        return None

    m3u_link = file_match.group(1)
    if "m3u" in m3u_link:
        m3u_link = m3u_link.replace("master.m3u8", "index.m3u8")
    return m3u_link


def get_streams(media_type, media_id, config=None):
    if not media_id or not media_id.startswith("http"):
        return []
    stream_url = _resolve(media_id)
    if not stream_url:
        return []
    return [
        {
            "name": TITLE,
            "title": TITLE,
            "url": stream_url,
            "behaviorHints": {
                "notMyMetadata": True,
                "proxyHeaders": {
                    "request": {
                        "User-Agent": USER_AGENT,
                        "Referer": MAIN_URL + "/",
                    }
                },
            },
        }
    ]