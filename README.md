# MegaSource Python Scrapers

Self-contained Python scrapers for the [MegaSource](https://github.com/zoreu/megasource_scrapers)
Stremio addon protocol. Each file is a complete `scraper.py` — upload it to
GitHub (or anywhere that serves raw files) and add the raw URL in the
MegaSource addon config page.

## Protocol

Every file implements:

```python
TITLE, VERSION, DESCRIPTION
get_streams(media_type: str, media_id: str, config: dict | None) -> list[dict]
```

- `media_type` : `"movie" | "series"`
- `media_id`   : `"tt0111161"` or `"tt0944947:1:1"`
- returns `[{ "name", "title", "url", "behaviorHints": { ... } }, ...]`

These scrapers are **listing scrapers** — they return the latest videos from a
site regardless of the queried title (the same approach as `test_scraper.py`).

## Files

| File               | Source site                        | Content type           |
|--------------------|------------------------------------|------------------------|
| `vidmax.py`        | https://vidmax.com                 | Latest clips           |
| `worldstar.py`     | https://worldstarhiphop.com        | Latest clips           |
| `kaotic.py`        | https://kaotic.com/recent          | Latest clips           |
| `livegore.py`      | https://www.livegore.com           | Latest clips           |
| `heavyfetish.py`   | https://heavyfetish.com (RSS)      | Latest clips           |
| `xrares.py`        | https://www.xrares.com             | Latest clips           |
| `nothingtoxic.py`  | https://nothingtoxic.com           | Latest clips           |
| `theync.py`        | https://theync.com                 | Latest clips           |
| `goregrish.py`     | https://goregrish.com              | Latest clips           |
| `usacrime.py`      | https://usacrime.com               | Latest clips           |
| `reddit.py`        | Reddit v.redd.it (3 subs default)  | Latest clips (HLS)     |
| `homemovies100.py` | https://www.homemovies100.it       | Latest clips           |
| `dailycommercials.py`| https://dailycommercials.com (RSS)| Latest clips           |
| `archiveorg.py`    | Archive.org movie collections      | Movies (direct MP4)    |
| `heavyr.py`        | https://www.heavy-r.com            | Latest clips           |
| `dailymotion.py`   | https://www.dailymotion.com        | Trending videos        |
| `youtube.py`       | YouTube channels (Piped/Invidious) | Latest uploads         |

## Config options

Each scraper accepts a `limit` in `config` (default 50):

```python
get_streams("movie", "tt0111161", {"limit": 100})
```

A few scrapers accept extra config:

- `reddit.py`: `{"subs": ["PublicFreakout", "fightporn"]}`
- `archiveorg.py`: `{"query": "collection:prelinger"}` (default: feature films)
- `dailymotion.py`: `{"channels": [["News", "news"], ["Music", "music"]]}` (name, channel id pairs)
- `youtube.py`: `{"channels": ["https://www.youtube.com/@handle/videos", ...]}`
- `usacrime.py` returns an empty list if Cloudflare blocks the request

## Local testing

```bash
python3 -c "
import importlib.util, json
spec = importlib.util.spec_from_file_location('s', 'vidmax.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
streams = m.get_streams('movie', 'tt0111161', {'limit': 3})
print(json.dumps(streams, indent=2))
"
```

## Requirements

Python 3.7+ — standard library only (`urllib`, `re`, `html`). No pip installs.
