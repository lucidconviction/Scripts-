"""
MegaSource scraper: Reddit
==========================
Protocol:
    TITLE, VERSION, DESCRIPTION
    get_streams(media_type: str, media_id: str, config: dict | None) -> list[dict]

Fetches the latest v.redd.it videos from a set of subreddits using Reddit's
public JSON API. Returns HLS playlists. Standard library only.

Config options:
    limit (int, default 50): max number of streams to return
    subs (list, default): override the subreddits to scrape
"""

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

TITLE = "Reddit"
VERSION = "1.0.0"
DESCRIPTION = "Latest v.redd.it videos from popular subs"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)

DEFAULT_SUBS = ["PublicFreakout", "fightporn", "CrazyFuckingVideos"]
MAX_VIDEOS_PER_SUB = 50


def _fetch(url, timeout=15):
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


def _extract_sub(subreddit):
    videos = []
    seen = set()
    after = ""
    for p in range(5):
        url = (
            f"https://www.reddit.com/r/{subreddit}/.json?limit=50"
            if p == 0
            else (
                f"https://www.reddit.com/r/{subreddit}/.json"
                f"?limit=50&after={urllib.parse.quote(after)}"
            )
        )
        body = _fetch(url)
        if not body:
            break
        try:
            data = json.loads(body)
        except (ValueError, TypeError):
            break
        children = (data.get("data") or {}).get("children") or []
        for child in children:
            d = child.get("data") or {}
            if not d or d.get("domain") != "v.redd.it":
                continue
            vid_id = d.get("id")
            if not vid_id or vid_id in seen:
                continue
            seen.add(vid_id)
            videos.append(
                (
                    (d.get("title") or "").strip(),
                    f"https://v.redd.it/{vid_id}/HLSPlaylist.m3u8",
                )
            )
        after = (data.get("data") or {}).get("after") or ""
        if not after:
            break
        time.sleep(1)
    return videos


def _scrape(limit, subs):
    streams = []
    seen = set()
    for sub in subs:
        for title, url in _extract_sub(sub):
            if url in seen:
                continue
            seen.add(url)
            streams.append(
                {
                    "name": f"r/{sub}",
                    "title": title or "Untitled",
                    "url": url,
                    "behaviorHints": {"notMyMetadata": True},
                }
            )
            if len(streams) >= limit:
                break
        if len(streams) >= limit:
            break
    return streams


def get_streams(media_type, media_id, config=None):
    limit = 50
    subs = DEFAULT_SUBS
    if isinstance(config, dict):
        try:
            limit = int(config.get("limit", limit))
        except (TypeError, ValueError):
            pass
        configured_subs = config.get("subs")
        if isinstance(configured_subs, list) and configured_subs:
            subs = configured_subs
    return _scrape(limit, subs)
