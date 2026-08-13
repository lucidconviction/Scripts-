"""
MegaSource scraper: VidHide (VidHidePro / EarnVids family)
==========================================================
Protocol:
    TITLE, VERSION, DESCRIPTION
    get_streams(media_type: str, media_id: str, config: dict | None) -> list[dict]

Resolves a file page on the VidHide family of sites (vidhide.com,
vidhidepro.com, vidhidehub.com, filelions.live/online/to, kinoger.be,
vidhidevip.com, vidhidepre.com, smoothpre.com, dhtpre.com, peytonepre.com,
ryderjet.com) to a direct stream URL. Unpacks P.A.C.K.E.R. scripts and
reads JWPlayer sources.

Pass the file URL as media_id. Standard library only.
"""

import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

TITLE = "VidHide"
VERSION = "1.0.0"
DESCRIPTION = "Resolve vidhide / filelions family links"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
MAIN_URL = "https://vidhidepro.com"

DOMAINS = [
    "vidhide.com",
    "vidhidepro.com",
    "vidhidehub.com",
    "filelions.live",
    "filelions.online",
    "filelions.to",
    "kinoger.be",
    "vidhidevip.com",
    "vidhidepre.com",
    "smoothpre.com",
    "dhtpre.com",
    "peytonepre.com",
    "ryderjet.com",
    "moflix-stream.click",
    "dinisglows.com",
]

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


def _extract_jwplayer(script, main_url):
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

    if not links:
        sources_match = re.search(r"sources:\s*(\[.*?\])", script, re.S)
        if sources_match:
            for file_match in re.finditer(
                r'file:\s*"([^"]+)"', sources_match.group(1), re.S
            ):
                links.append(file_match.group(1))

    return links


def _fetch(url, timeout=20, retries=3, headers=None, referer=None):
    h = {
        "User-Agent": USER_AGENT,
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "cross-site",
        "Accept": "*/*",
    }
    origin = urllib.parse.urlparse(url).scheme + "://" + urllib.parse.urlparse(url).netloc
    h["Origin"] = origin
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


def _get_embed_url(url):
    for needle in ("/d/", "/download/", "/file/", "/f/"):
        if needle in url:
            return url.replace(needle, "/v/")
    return url.replace("/e/", "/v/")


def _resolve(url):
    main_url = urllib.parse.urlparse(url).scheme + "://" + urllib.parse.urlparse(url).netloc
    embed_url = _get_embed_url(url)
    page = _fetch(embed_url, referer=url)
    if not page:
        return []

    script_data = ""
    if _js_unpack(page):
        script_data = _js_unpack(page)
    else:
        for script_match in re.finditer(
            r"<script[^>]*>([\s\S]*?)</script>", page, re.I
        ):
            if "sources:" in script_match.group(1):
                script_data = script_match.group(1)
                break

    return _extract_jwplayer(script_data, main_url) if script_data else []


def get_streams(media_type, media_id, config=None):
    if not media_id or not media_id.startswith("http"):
        return []
    parsed = urllib.parse.urlparse(media_id)
    main_url = f"{parsed.scheme}://{parsed.netloc}"
    links = _resolve(media_id)
    streams = []
    for url in links:
        if url.startswith("//"):
            url = "https:" + url
        elif url.startswith("/"):
            url = main_url + url
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