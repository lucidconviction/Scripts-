"""
MegaSource scraper: Maxstream
=============================
Protocol:
    TITLE, VERSION, DESCRIPTION
    get_streams(media_type: str, media_id: str, config: dict | None) -> list[dict]

Resolves a file page on maxstream.video to a direct stream URL by unpacking
the embedded P.A.C.K.E.R. script and reading the `src:"...",type` value.

Pass the file URL as media_id. Standard library only.
"""

import re
import time
import urllib.error
import urllib.parse
import urllib.request

TITLE = "Maxstream"
VERSION = "1.0.0"
DESCRIPTION = "Resolve maxstream.video links"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
MAIN_URL = "https://maxstream.video"

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


def _resolve(url):
    page = _fetch(url)
    if not page:
        return None

    src_match = re.search(r'src\s*:\s*"((?:.|\n)*?)",\s*type', page)
    if src_match:
        return src_match.group(1).strip()

    eval_match = re.search(r"cript\">eval((?:.|\n)*?)</script>", page, re.S)
    if not eval_match:
        return None

    unpacked = _js_unpack(eval_match.group(1))
    if not unpacked:
        return None

    src_match = re.search(r'src\s*:\s*"((?:.|\n)*?)",\s*type', unpacked)
    if not src_match:
        return None

    return src_match.group(1).strip()


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
