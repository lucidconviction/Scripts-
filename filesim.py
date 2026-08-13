"""
MegaSource scraper: Filesim (Streamhide / Movhide / Ztreamhub ...)
==================================================================
Protocol:
    TITLE, VERSION, DESCRIPTION
    get_streams(media_type: str, media_id: str, config: dict | None) -> list[dict]

Resolves a file page on files.im / streamhide.to / streamhide.com /
movhide.pro / ztreamhub.com / multimoviesshg.com / guccihide.com /
ahvsh.com / moviesm4u.com to a direct stream URL.

Pass the file URL as media_id:

    get_streams("movie", "https://streamhide.to/e/abc123")

Unpacks P.A.C.K.E.R. scripts and reads JWPlayer sources. Standard library only.
"""

import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

TITLE = "Filesim"
VERSION = "1.0.0"
DESCRIPTION = "Resolve Filesim family links (streamhide, movhide, files.im)"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
MAIN_URL = "https://files.im"

_ALPHABET_62 = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_ALPHABET_95 = " !\"#$%&\\'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~"


def _js_unpack(packed_js):
    if not packed_js:
        return None
    match = re.search(
        r"}\s*\('(.*)',\s*(.*?),\s*(\d+),\s*'(.*?)'\.split\('\|'\)", packed_js, re.S
    )
    if not match:
        return None
    payload = match.group(1).replace("\\'", "'")
    try:
        radix = int(match.group(2))
    except (ValueError, TypeError):
        radix = 36
    count = int(match.group(3))
    symtab = match.group(4).split("|")
    if len(symtab) != count:
        return None

    if radix > 36:
        if radix < 62:
            alphabet = _ALPHABET_62[:radix]
        elif radix == 62:
            alphabet = _ALPHABET_62
        elif 63 <= radix <= 94:
            alphabet = _ALPHABET_95[:radix]
        elif radix == 95:
            alphabet = _ALPHABET_95
        else:
            alphabet = None
        dictionary = {ch: i for i, ch in enumerate(alphabet)} if alphabet else None
    else:
        dictionary = None

    def unbase(word):
        if dictionary is None:
            try:
                return int(word, radix)
            except ValueError:
                return 0
        total = 0
        for i, ch in enumerate(reversed(word)):
            total += radix ** i * dictionary.get(ch, 0)
        return total

    decoded = payload
    replace_offset = 0
    for word_match in re.finditer(r"\b[a-zA-Z0-9_]+\b", payload):
        word = word_match.group(0)
        x = unbase(word)
        value = symtab[x] if 0 <= x < len(symtab) else None
        if value:
            start = word_match.start() + replace_offset
            end = word_match.end() + replace_offset
            decoded = decoded[:start] + value + decoded[end:]
            replace_offset += len(value) - len(word)
    return decoded


def _extract_jwplayer(script, page_url):
    """Extract stream URLs from a JWPlayer setup script."""
    links = []

    source_match = re.search(r'"sources"?\s*:\s*(\[.*?\])', script, re.S)
    if source_match:
        raw = source_match.group(1)
        try:
            sources = json.loads(raw)
            for source in sources:
                file_url = source.get("file")
                if file_url:
                    links.append(file_url)
        except (ValueError, TypeError):
            for file_match in re.finditer(r'"file"\s*:\s*"([^"]+)"', raw, re.S):
                links.append(file_match.group(1))

    if not links:
        for file_match in re.finditer(
            r'[:=]\s*"([^"\s]+(?:\.m3u8|master\.txt)[^"\s]*)"', script
        ):
            links.append(file_match.group(1))

    return links


def _fetch(url, timeout=20, retries=3, headers=None, referer=None):
    h = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html",
        "Accept-Language": "en-US,en;q=0.5",
    }
    if referer:
        h["Referer"] = referer
    if headers:
        h.update(headers)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            return exc.read().decode("utf-8", errors="replace")
        except Exception:
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
    return ""


def _resolve(url):
    embed_url = url.replace("/download/", "/e/")
    page = _fetch(embed_url, referer=url)
    if not page:
        return []

    iframe_match = re.search(r'<iframe[^>]*src="([^"]+)"', page, re.I)
    if iframe_match:
        iframe_url = urllib.parse.urljoin(embed_url, iframe_match.group(1))
        page = _fetch(
            iframe_url,
            headers={"Sec-Fetch-Dest": "iframe"},
            referer=embed_url,
        )

    script_data = ""
    if _js_unpack(page):
        script_data = _js_unpack(page)
    else:
        script_match = re.search(r"<script[^>]*>([\s\S]*?sources:[\s\S]*?)</script>", page, re.I)
        if script_match:
            script_data = script_match.group(1)

    links = _extract_jwplayer(script_data, embed_url) if script_data else []
    return links


def get_streams(media_type, media_id, config=None):
    if not media_id or not media_id.startswith("http"):
        return []
    links = _resolve(media_id)
    streams = []
    for url in links:
        streams.append(
            {
                "name": TITLE,
                "title": TITLE,
                "url": url,
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
