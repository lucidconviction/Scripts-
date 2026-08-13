"""
MegaSource scraper: Videa
=========================
Protocol:
    TITLE, VERSION, DESCRIPTION
    get_streams(media_type: str, media_id: str, config: dict | None) -> list[dict]

Resolves a video page on videa.hu to direct stream URLs. Handles the
encrypted XML responses and RC4 decryption.

Pass the video URL as media_id. Standard library only.
"""

import base64
import html as _html
import re
import time
import urllib.error
import urllib.parse
import urllib.request

TITLE = "Videa"
VERSION = "1.0.0"
DESCRIPTION = "Resolve videa.hu links"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
MAIN_URL = "https://videa.hu"

_VIDEA_SECRET = "xHb0ZvME5q8CBcoQi6AngerDu3FGO9fkUlwPmLVY_RTzj2hJIS4NasXWKy1td7p"


def _fetch(url, timeout=20, retries=3, headers=None, referer=None, raw=False):
    h = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if referer:
        h["Referer"] = referer
    if headers:
        h.update(headers)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
                return (body if raw else body.decode("utf-8", errors="replace"),
                        resp.headers)
        except urllib.error.HTTPError as exc:
            body = exc.read()
            return (body if raw else body.decode("utf-8", errors="replace"),
                    exc.headers)
        except Exception:
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
    return (b"" if raw else "", None)


def _generate_tokens(nonce):
    lo = nonce[:32]
    s = nonce[32:]
    result = ""
    for i in range(32):
        index = _VIDEA_SECRET.index(lo[i]) - 31
        result += s[i - index]

    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    random_seed = "".join(chars[int(time.time() * 1000 + i * 7) % len(chars)] for i in range(8))
    key = result[16:] + random_seed
    return random_seed, result[:16], key


def _rc4_decrypt(encrypted_bytes, key):
    printable = all(32 <= (b & 0xFF) <= 126 or b in (10, 13) for b in encrypted_bytes)
    if printable:
        base64_string = (
            encrypted_bytes.decode("utf-8", errors="replace")
            .replace("\r", "")
            .replace("\n", "")
            .replace(" ", "")
            .strip()
        )
        try:
            encrypted_bytes = base64.b64decode(base64_string)
        except Exception:
            pass

    key_bytes = key.encode("utf-8")
    s = list(range(256))
    j = 0
    for i in range(256):
        j = (j + s[i] + key_bytes[i % len(key_bytes)]) % 256
        s[i], s[j] = s[j], s[i]

    i = 0
    j = 0
    result = bytearray(len(encrypted_bytes))
    for k in range(len(encrypted_bytes)):
        i = (i + 1) % 256
        j = (j + s[i]) % 256
        s[i], s[j] = s[j], s[i]
        result[k] = encrypted_bytes[k] ^ s[(s[i] + s[j]) % 256]
    return bytes(result).decode("utf-8", errors="replace")


def _get_xml_url(url):
    html, _ = _fetch(url)
    if not html:
        return None, None

    if "/player" in url or "/looper" in url:
        player_url = url
    else:
        iframe = re.search(r'<iframe.*?src="((?:/player|/looper)\?[^"]+)', html)
        if not iframe:
            return None, None
        player_url = MAIN_URL + _html.unescape(iframe.group(1))

    player_html, _ = _fetch(player_url)
    if not player_html:
        return None, None

    nonce_match = re.search(r'_xt\s*=\s*"([^"]+)', player_html)
    if not nonce_match:
        return None, None

    random_seed, t_token, gen_key = _generate_tokens(nonce_match.group(1))

    if "f=" in player_url:
        video_param = "f=" + player_url.split("f=")[1].split("&")[0]
    elif "v=" in player_url:
        video_param = "v=" + player_url.split("v=")[1].split("&")[0]
    elif "b=" in player_url:
        video_param = "b=" + player_url.split("b=")[1].split("&")[0]
    else:
        return None, None

    xml_url = f"{MAIN_URL}/player/xml?platform=desktop&{video_param}&_s={random_seed}&_t={t_token}"
    return xml_url, gen_key

def _parse_sources(xml):
    links = []
    for source_match in re.finditer(
        r'<video_source\s+name="([^"]+)"[^>]*>([^<]+)</video_source>', xml
    ):
        source_name = source_match.group(1)
        source_url = source_match.group(2).strip()
        if source_url.startswith("//"):
            source_url = "https:" + source_url
        source_url = _html.unescape(source_url)
        links.append({"url": source_url, "name": source_name})

    if links:
        return links

    source_regex = re.compile(
        r'video_source\s*name="([^"]+)".*exp="([^"]+)"[^>]*>([^<]+)'
    )
    for source_match in source_regex.finditer(xml):
        source_name = source_match.group(1)
        exp = source_match.group(2)
        source_url = source_match.group(3)
        if source_url.startswith("//"):
            source_url = "https:" + source_url

        hash_match = re.search(rf"<hash_value_{source_name}>([^<]+)<", xml)
        if not hash_match:
            continue
        final_url = f"{source_url}?md5={hash_match.group(1)}&expires={exp}".replace("&amp;", "&")
        links.append({"url": final_url, "name": source_name})
    return links


def _resolve(url):
    current_url = url
    key = ""
    visited = set()
    count = 10
    while current_url not in visited and count > 0:
        visited.add(current_url)
        count -= 1

        web_url, gen_key = _get_xml_url(current_url)
        if not web_url:
            return []
        response, resp_headers = _fetch(web_url, raw=True)
        if not response:
            return []

        is_xml = (
            len(response) >= 5
            and response[0] == 0x3C
            and response[1] == 0x3F
            and response[2] == 0x78
            and response[3] == 0x6D
            and response[4] == 0x6C
        )

        if is_xml:
            videa_xml = response.decode("utf-8", errors="replace")
        else:
            if not resp_headers:
                return []
            xs_header = resp_headers.get("X-Videa-Xs") or ""
            if not xs_header:
                return []
            key = gen_key + xs_header
            videa_xml = _rc4_decrypt(response, key)

        redirect_match = re.search(r"<error.*?noembed.*>(.*)</error>", videa_xml)
        if redirect_match and redirect_match.group(1) != current_url:
            current_url = redirect_match.group(1)
        else:
            return _parse_sources(videa_xml)
    return []


def get_streams(media_type, media_id, config=None):
    if not media_id or not media_id.startswith("http"):
        return []
    links = _resolve(media_id)
    streams = []
    for link in links:
        streams.append(
            {
                "name": TITLE,
                "title": f"{link['name']} - {TITLE}",
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