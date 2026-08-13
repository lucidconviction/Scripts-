"""
MegaSource scraper: Vicloud
===========================
Protocol:
    TITLE, VERSION, DESCRIPTION
    get_streams(media_type: str, media_id: str, config: dict | None) -> list[dict]

Resolves a file page on vicloud.sbs to direct stream URLs via its API.

Pass the file URL as media_id. Standard library only.
"""

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

TITLE = "Vicloud"
VERSION = "1.0.0"
DESCRIPTION = "Resolve vicloud.sbs links"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
MAIN_URL = "https://vicloud.sbs"


def _fetch(url, timeout=20, retries=3, headers=None, referer=None):
    h = {"User-Agent": USER_AGENT, "Accept": "*/*"}
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
        return []

    api_query = re.search(r'"apiQuery":"(.*?)"', page)
    if not api_query:
        return []

    unix_ms = str(int(time.time() * 1000))
    api_url = f"{MAIN_URL}/api/?{api_query.group(1)}&_={unix_ms}"
    body = _fetch(
        api_url,
        headers={"X-Requested-With": "XMLHttpRequest"},
        referer=url,
    )
    if not body:
        return []

    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        return []

    links = []
    for source in data.get("sources") or []:
        file_url = source.get("file")
        if file_url:
            links.append(
                {
                    "url": file_url,
                    "quality": source.get("label"),
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
                            "Referer": media_id,
                        }
                    },
                },
            }
        )
    return streams
