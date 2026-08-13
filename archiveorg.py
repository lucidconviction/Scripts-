"""
MegaSource scraper: Archive.org
===============================
Protocol:
    TITLE, VERSION, DESCRIPTION
    get_streams(media_type: str, media_id: str, config: dict | None) -> list[dict]

Searches Archive.org's advanced search for movies and resolves direct .mp4
download URLs from item metadata. Standard library only.

Config options:
    limit (int, default 20): max number of streams to return
    query (str, default): override the search query / collection
"""

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

TITLE = "Archive.org"
VERSION = "1.0.0"
DESCRIPTION = "Movies from Archive.org collections"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)

DEFAULT_QUERY = "collection:feature_films OR collection:moviesandfilms"


def _fetch(url, timeout=20, retries=3):
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
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


def _find_mp4(files):
    preferred = [
        f for f in files
        if f.get("name", "").endswith(".mp4") and ".ia.mp4" not in f.get("name", "")
    ]
    if not preferred:
        preferred = [f for f in files if f.get("name", "").endswith(".mp4")]
    return preferred[0]["name"] if preferred else None


def _scrape(limit, query):
    search_url = (
        "https://archive.org/advancedsearch.php?q="
        + urllib.parse.quote(query + " AND mediatype:movies")
        + "&fl[]=identifier&fl[]=title&sort[]=downloads+desc"
        + f"&rows={limit}&output=json"
    )
    body = _fetch(search_url)
    if not body:
        return []

    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        return []

    docs = (data.get("response") or {}).get("docs") or []
    streams = []
    seen = set()

    for doc in docs:
        identifier = doc.get("identifier")
        title = doc.get("title")
        if not identifier or not title or identifier in seen:
            continue
        seen.add(identifier)

        meta_body = _fetch(f"https://archive.org/metadata/{identifier}")
        mp4_name = None
        if meta_body:
            try:
                meta = json.loads(meta_body)
                mp4_name = _find_mp4(meta.get("files") or [])
            except (ValueError, TypeError):
                pass

        if mp4_name:
            stream_url = (
                f"https://archive.org/download/{identifier}/"
                + urllib.parse.quote(mp4_name)
            )
        else:
            stream_url = f"https://archive.org/download/{identifier}/{identifier}.mp4"

        streams.append(
            {
                "name": TITLE,
                "title": title,
                "url": stream_url,
                "behaviorHints": {
                    "notMyMetadata": True,
                    "proxyHeaders": {"request": {"User-Agent": USER_AGENT}},
                },
            }
        )
        if len(streams) >= limit:
            break

    return streams


def get_streams(media_type, media_id, config=None):
    limit = 20
    query = DEFAULT_QUERY
    if isinstance(config, dict):
        try:
            limit = int(config.get("limit", limit))
        except (TypeError, ValueError):
            pass
        configured_query = config.get("query")
        if isinstance(configured_query, str) and configured_query:
            query = configured_query
    return _scrape(limit, query)
