"""
MegaSource scraper: HomeMovies100
=================================
Protocol:
    TITLE, VERSION, DESCRIPTION
    get_streams(media_type: str, media_id: str, config: dict | None) -> list[dict]

Scrapes https://www.homemovies100.it/en/ for direct .mp4 URLs embedded in the
window.__QUERY_STATE__ payload. Standard library only.

Config options:
    limit (int, default 50): max number of streams to return
"""

import json
import re
import time
import urllib.error
import urllib.request

TITLE = "HomeMovies100"
VERSION = "1.0.0"
DESCRIPTION = "Latest videos from homemovies100.it"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
BASE_URL = "https://www.homemovies100.it"


def _fetch(url, timeout=20, retries=3):
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html"}
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


def _walk(state):
    """Yield every dict in the nested structure that may hold url_content."""
    stack = [state]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            yield item
            for value in item.values():
                if isinstance(value, (dict, list)):
                    stack.append(value)
        elif isinstance(item, list):
            for value in item:
                if isinstance(value, (dict, list)):
                    stack.append(value)


def _scrape(limit):
    page = _fetch(BASE_URL + "/en/")
    if not page:
        return []

    match = re.search(r"window\.__INITIAL_DATA__\s*=\s*(\{[\s\S]*?\});", page)
    if not match:
        return []

    try:
        state = json.loads(match.group(1))
    except (ValueError, TypeError):
        return []

    streams = []
    seen = set()
    for item in _walk(state):
        url_content = item.get("url_content")
        if not isinstance(url_content, str) or ".mp4" not in url_content:
            continue
        if url_content in seen:
            continue
        seen.add(url_content)
        title = item.get("title") or item.get("name") or "Untitled"
        if isinstance(title, dict):
            title = title.get("en") or title.get("it") or next(iter(title.values()), "Untitled")
        streams.append(
            {
                "name": TITLE,
                "title": title,
                "url": url_content,
                "behaviorHints": {
                    "notMyMetadata": True,
                    "proxyHeaders": {
                        "request": {
                            "User-Agent": USER_AGENT,
                            "Referer": BASE_URL + "/en/",
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
