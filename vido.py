"""
MegaSource scraper: Vido
========================
Protocol:
    TITLE, VERSION, DESCRIPTION
    get_streams(media_type: str, media_id: str, config: dict | None) -> list[dict]

Resolves a file page on vido.lol to a direct stream URL by converting the
URL to the /embed- form and reading the `sources` array.

Pass the file URL as media_id. Standard library only.
"""

import re
import time
import urllib.error
import urllib.parse
import urllib.request

TITLE = "Vido"
VERSION = "1.0.0"
DESCRIPTION = "Resolve vido.lol links"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
MAIN_URL = "https://vido.lol"


def _fetch(url, timeout=20, retries=3, headers=None, referer=None):
    h = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
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
    embed_url = url.replace("/e/", "/embed-")
    page = _fetch(embed_url, referer=url)
    if not page:
        return None

    source_match = re.search(r'sources:\s*\["(.*?)"\]', page)
    if not source_match:
        return None

    return source_match.group(1).strip()


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