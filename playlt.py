"""
MegaSource scraper: PlayLt
==========================
Protocol:
    TITLE, VERSION, DESCRIPTION
    get_streams(media_type: str, media_id: str, config: dict | None) -> list[dict]

Resolves a file page on play.playlt.xyz to a direct stream URL via the
PlayLt API.

Pass the file URL as media_id. Standard library only.
"""

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

TITLE = "PlayLt"
VERSION = "1.0.0"
DESCRIPTION = "Resolve play.playlt.xyz links"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
MAIN_URL = "https://play.playlt.xyz"
API_URL = "https://api-plhq.playlt.xyz"


def _fetch(url, timeout=20, retries=3, data=None, headers=None, referer=None):
    h = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if referer:
        h["Referer"] = referer
    if headers:
        h.update(headers)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            return exc.read().decode("utf-8", errors="replace")
        except Exception:
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
    return ""


def _resolve(url):
    page = _fetch(url, referer=url)
    if not page:
        return None

    body_text = ""
    for script in re.finditer(r"<script[^>]*>([\s\S]*?)</script>", page, re.I):
        if "var idUser" in script.group(1):
            body_text = script.group(1)
            break

    if not body_text:
        return None

    id_user = re.search(r'var idUser = "([^"]*)"', body_text)
    id_file = re.search(r'var idfile = "([^"]*)"', body_text)
    if not id_user or not id_file or not id_user.group(1) or not id_file.group(1):
        return None

    post_url = f"{API_URL}/apiv5/{id_user.group(1)}/{id_file.group(1)}"
    data = "referrer=" + urllib.parse.quote(url, safe="") + "&typeend=html"
    body = _fetch(
        post_url,
        data=data.encode(),
        headers={
            "Origin": MAIN_URL,
            "Referer": MAIN_URL + "/",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        },
    )
    if not body:
        return None

    try:
        item = json.loads(body)
    except (ValueError, TypeError):
        return None

    return item.get("data") if item.get("data") else None


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
                        "Referer": media_id,
                    }
                },
            },
        }
    ]