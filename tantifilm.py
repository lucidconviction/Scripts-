"""
MegaSource scraper: Tantifilm (Cercafilm)
=========================================
Protocol:
    TITLE, VERSION, DESCRIPTION
    get_streams(media_type: str, media_id: str, config: dict | None) -> list[dict]

Resolves a file page on cercafilm.net to direct stream URLs via its
`/api/source/` endpoint.

Pass the file URL as media_id. Standard library only.
"""

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

TITLE = "Tantifilm"
VERSION = "1.0.0"
DESCRIPTION = "Resolve cercafilm.net (tantifilm) links"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
MAIN_URL = "https://cercafilm.net"


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
    video_id = url.rstrip("/").split("/")[-1]
    api_url = f"{MAIN_URL}/api/source/{video_id}"
    body = _fetch(
        api_url,
        data=b"r=&d=" + urllib.parse.quote(MAIN_URL, safe="").encode(),
        headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
        },
        referer=url,
    )
    if not body:
        return []

    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        match = re.search(r'"file"\s*:\s*"([^"]+)"', body)
        return [match.group(1)] if match else []

    links = []
    for source in data.get("data") or []:
        file_url = source.get("file")
        if file_url:
            stream_file = file_url
            label = source.get("label")
            if "m3u8" in file_url.lower() or "mp4" in file_url.lower():
                stream_file = file_url
            links.append(
                {
                    "url": stream_file,
                    "quality": label,
                }
            )
    return links


def get_streams(media_type, media_id, config=None):
    if not media_id or not media_id.startswith("http"):
        return []
    links = _resolve(media_id)
    streams = []
    for link in links:
        streams.append(
            {
                "name": TITLE,
                "title": link.get("quality") or TITLE,
                "url": link["url"],
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
        )
    return streams