"""
MegaSource scraper: LiveGore
============================
Protocol:
    TITLE, VERSION, DESCRIPTION
    get_streams(media_type: str, media_id: str, config: dict | None) -> list[dict]

Scrapes https://www.livegore.com/ for the latest posts and resolves direct
.mp4 URLs from each post page. Falls back to alternate domains if the main
one returns nothing. Standard library only.

Config options:
    limit (int, default 50): max number of streams to return
"""

import concurrent.futures
import html
import re
import time
import urllib.error
import urllib.request

TITLE = "LiveGore"
VERSION = "1.0.0"
DESCRIPTION = "Latest videos from livegore.com"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
BASE_URL = "https://www.livegore.com"
ALT_DOMAINS = ["https://livegore.net/", "https://livegore.org/"]


def _fetch(url, timeout=15, retries=3):
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html",
        "Referer": BASE_URL + "/",
    }
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


def _extract_post_links(html_text):
    links = []
    seen = set()
    regexes = [
        r'<a[^>]*href="(https://www\.livegore\.com/\d+[^"]*)"[^>]*>',
        r'<a\s+class="[^"]*post[^"]*"[^>]*href="([^"]+)"',
        r'data-link="([^"]+)"',
    ]
    for pattern in regexes:
        for match in re.finditer(pattern, html_text, re.I):
            url = match.group(1).split("?")[0].split("#")[0]
            if url and url not in seen:
                seen.add(url)
                links.append(url)

    fallback = re.finditer(
        r'<a[^>]*href="([^"]*)"[^>]*>[^<]*(?:<[^>]*>[^<]*)*</a>', html_text, re.I
    )
    for match in fallback:
        url = match.group(1).split("?")[0].split("#")[0]
        if url and url not in seen:
            seen.add(url)
            links.append(url)

    return links


def _resolve_video_page(video_url):
    page = _fetch(video_url)
    if not page:
        return None

    patterns = [
        r'<source[^>]+src="([^"]+\.mp4)"',
        r'<video[^>]*src="([^"]+\.mp4)"',
        r'src=["\']([^"\']+\.mp4)["\']',
        r'data-src="([^"]+\.mp4)"',
    ]
    src_match = None
    for pattern in patterns:
        src_match = re.search(pattern, page, re.I)
        if src_match:
            break
    if not src_match:
        return None

    mp4_url = src_match.group(1).split("?")[0]

    title_match = re.search(
        r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', page, re.I
    )
    if not title_match:
        title_match = re.search(
            r'<meta[^>]+name="description"[^>]+content="([^"]*?)"', page, re.I
        )
    if not title_match:
        title_match = re.search(r"<title>([^<]*)</title>", page, re.I)

    title = (
        html.unescape(title_match.group(1)).strip()
        if title_match
        else "Untitled"
    )
    return title, mp4_url


def _scrape(limit):
    page_urls = [BASE_URL + "/"] + [
        f"{BASE_URL}/?start={i * 20}" for i in range(1, 5)
    ]

    post_links = []
    for page_url in page_urls:
        page = _fetch(page_url)
        if page:
            for link in _extract_post_links(page):
                if link not in post_links:
                    post_links.append(link)

    if not post_links:
        for alt in ALT_DOMAINS:
            page = _fetch(alt)
            if page:
                for link in _extract_post_links(page):
                    if link not in post_links:
                        post_links.append(link)

    resolved = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = {
            pool.submit(_resolve_video_page, video_url): video_url
            for video_url in post_links[:limit]
        }
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
            except Exception:
                result = None
            if result:
                resolved.append(result)

    streams = []
    for title, mp4_url in resolved:
        streams.append(
            {
                "name": TITLE,
                "title": title,
                "url": mp4_url,
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
