# api_client.py (v2)
# Klien HadeethEnc API: satu session bersama, cache, retry, dan indeks pencarian judul.
# Kegagalan API melempar ApiError (tidak lagi disamarkan sebagai data kosong).
import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import aiohttp

logger = logging.getLogger(__name__)

BASE = "https://hadeethenc.com/api/v1"
CACHE_TTL = 3600          # detik
CACHE_MAX = 500
TIMEOUT = 15
INDEX_FILE = Path(__file__).resolve().parent / "index_hadist.json"
INDEX_PER_PAGE = 50
RETRY_STATUS = (429, 500, 502, 503, 504)


class ApiError(Exception):
    """Gagal mengambil data dari HadeethEnc."""


_session: Optional[aiohttp.ClientSession] = None
_cache: Dict[Tuple, Tuple[float, Any]] = {}
_index: Optional[Dict[str, str]] = None
_index_lock = asyncio.Lock()


def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(headers={"User-Agent": "bot-hadist/2.0"})
    return _session


async def close() -> None:
    if _session is not None and not _session.closed:
        await _session.close()


async def _get_json(path: str, use_cache: bool = True, **params) -> Any:
    key = (path, tuple(sorted(params.items())))
    if use_cache:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < CACHE_TTL:
            return hit[1]
    url = f"{BASE}/{path}"
    last: Optional[Exception] = None
    for attempt in range(3):
        try:
            async with _get_session().get(
                url, params=params, timeout=aiohttp.ClientTimeout(total=TIMEOUT)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    if use_cache:
                        if len(_cache) >= CACHE_MAX:
                            _cache.clear()
                        _cache[key] = (time.time(), data)
                    return data
                last = ApiError(f"HTTP {resp.status}")
                if resp.status not in RETRY_STATUS:
                    break
        except (asyncio.TimeoutError, aiohttp.ClientError, ValueError) as e:
            last = ApiError(str(e) or type(e).__name__)
        await asyncio.sleep(1.5 * (attempt + 1))
    logger.warning("API gagal: %s (%s)", path, last)
    raise last if isinstance(last, ApiError) else ApiError("gagal")


async def get_categories_roots(language: str = "id") -> List[Dict[str, Any]]:
    return await _get_json("categories/roots/", language=language)


async def get_categories_list(language: str = "id") -> List[Dict[str, Any]]:
    return await _get_json("categories/list/", language=language)


async def get_hadiths_list(language: str = "id", category_id: Optional[int] = None,
                           page: int = 1, per_page: int = 10,
                           use_cache: bool = True) -> Dict[str, Any]:
    params: Dict[str, Any] = {"language": language, "page": page, "per_page": per_page}
    if category_id is not None:
        params["category_id"] = category_id
    return await _get_json("hadeeths/list/", use_cache=use_cache, **params)


async def get_hadith_one(hadith_id: int, language: str = "id") -> Dict[str, Any]:
    return await _get_json("hadeeths/one/", id=hadith_id, language=language)


# ---------- indeks pencarian (judul saja) ----------

async def build_index(language: str = "id") -> Dict[str, str]:
    """Kumpulkan id -> judul semua hadist dari semua kategori."""
    cats = await get_categories_list(language)
    sem = asyncio.Semaphore(4)
    found: Dict[str, str] = {}

    async def crawl(cat_id) -> None:
        page = 1
        while page <= 300:
            try:
                async with sem:
                    data = await get_hadiths_list(language, cat_id, page,
                                                  INDEX_PER_PAGE, use_cache=False)
            except ApiError:
                logger.warning("Lewati kategori %s halaman %s", cat_id, page)
                return
            items = data.get("data", [])
            for h in items:
                found[str(h.get("id"))] = h.get("title", "")
            try:
                last = int((data.get("meta") or {}).get("last_page") or 0)
            except (TypeError, ValueError):
                last = 0
            if not items or (last and page >= last) or (not last and len(items) < INDEX_PER_PAGE):
                return
            page += 1

    await asyncio.gather(*(crawl(c.get("id")) for c in cats))
    return found


def _save_index(index: Dict[str, str]) -> None:
    INDEX_FILE.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")


async def get_index(on_build: Optional[Callable] = None) -> Dict[str, str]:
    global _index
    if _index is not None:
        return _index
    async with _index_lock:
        if _index is None:
            if INDEX_FILE.is_file():
                _index = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
            else:
                if on_build:
                    await on_build()
                _index = await build_index()
                _save_index(_index)
    return _index


async def refresh_index() -> int:
    global _index
    async with _index_lock:
        _index = await build_index()
        _save_index(_index)
        return len(_index)


def search_index(index: Dict[str, str], query: str) -> List[Tuple[str, str]]:
    words = [w for w in query.lower().split() if w]
    if not words:
        return []
    return [(i, t) for i, t in index.items()
            if all(w in (t or "").lower() for w in words)]
