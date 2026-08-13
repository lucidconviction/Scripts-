"""
MegaSource scraper: DoodStream
==============================
Protocol:
    TITLE, VERSION, DESCRIPTION
    get_streams(media_type: str, media_id: str, config: dict | None) -> list[dict]

Resolves a DoodStream file page (dood.la, d0000d.com, doodstream.com, etc.)
to a direct stream URL. Pass the file URL as media_id, e.g.

    get_streams("movie", "https://dood.la/d/abc123")

Standard library only.
"""

import random
import re
import string
import time
import urllib.error
import urllib.parse
import urllib.request

TITLE = "DoodStream"
VERSION = "1.0.0"
DESCRIPTION = "Resolve DoodStream file links (dood.la, d0000d, doodstream, ...)"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
BASE_URL = "https://dood.la"
ALPHABET = string.ascii_letters + string.digits


def _fetch(url, timeout=20, retries=3, headers=None, referer=None):
    h = {"User-Agent": USER_AGENT, "Accept": "text/html"}
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


def _get_base_url(url):
    parsed = urllib.parse.urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _resolve(url):
    embed_url = url.replace("/d/", "/e/")
    page = _fetch(embed_url)
    if not page:
        return None

    host = _get_base_url(embed_url)
    pass_md5 = re.search(r"/pass_md5/[^'\"]*", page)
    if not pass_md5:
        return None

    md5_url = host + pass_md5.group(0)
    token_text = _fetch(md5_url, referer=embed_url).strip()
    if not token_text:
        return None

    random_suffix = "".join(random.choice(ALPHABET) for _ in range(10))
    stream_url = token_text + random_suffix + "?token=" + md5_url.split("/")[-1]

    quality_match = re.search(
        r"<title>([^<]*)</title>", page, re.I
    )
    quality = None
    if quality_match:
        q = re.search(r"\d{3,4}p", quality_match.group(1))
        quality = q.group(0) if q else None

    return stream_url, quality, embed_url


def get_streams(media_type, media_id, config=None):
    if not media_id or not media_id.startswith("http"):
        return []
    result = _resolve(media_id)
    if not result:
        return []
    stream_url, quality, embed_url = result
    return [
        {
            "name": TITLE,
            "title": quality or TITLE,
            "url": stream_url,
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
    ]
