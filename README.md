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

| File             | Source site                     | Content type |
|------------------|---------------------------------|--------------|
| `vidmax.py`      | https://vidmax.com              | Latest clips |
| `worldstar.py`   | https://worldstarhiphop.com     | Latest clips |
| `kaotic.py`      | https://kaotic.com/recent       | Latest clips |
| `livegore.py`    | https://www.livegore.com        | Latest clips |
| `heavyfetish.py` | https://heavyfetish.com (RSS)   | Latest clips |
| `xrares.py`      | https://www.xrares.com          | Latest clips |
| `nothingtoxic.py`| https://nothingtoxic.com        | Latest clips |

## Config options

Each scraper accepts a `limit` in `config` (default 50):

```python
get_streams("movie", "tt0111161", {"limit": 100})
```

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
