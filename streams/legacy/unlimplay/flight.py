"""
Utilidades de concurrencia para la Activity.

- SingleFlight / TTLCache
- resolve_stream() → registry multi-provider (modules.providers)

Política de idiomas (NO mezclar):
  • Español  → videoapi → embed69 → playlatinsrc → (opcional) unlimplay
  • Inglés   → vidsrc → vidapi → vixsrc → vaplayer → vidlink
"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any, Callable, Hashable, Optional, Tuple


class TTLCache:
    """Caché LRU con TTL y límite aproximado de bytes."""

    def __init__(self, ttl: float, max_bytes: int = 0, max_items: int = 256):
        self.ttl = ttl
        self.max_bytes = max_bytes
        self.max_items = max_items
        self._d: "OrderedDict[Hashable, Tuple[float, Any, int]]" = OrderedDict()
        self._bytes = 0
        self._lock = threading.Lock()

    def get(self, key: Hashable) -> Optional[Any]:
        now = time.time()
        with self._lock:
            item = self._d.get(key)
            if not item:
                return None
            ts, val, size = item
            if now - ts > self.ttl:
                self._d.pop(key, None)
                self._bytes -= size
                return None
            self._d.move_to_end(key)
            return val

    def set(
        self, key: Hashable, val: Any, size: int = 0, ttl: Optional[float] = None
    ) -> None:
        ts = time.time()
        if ttl is not None:
            ts = ts - (self.ttl - ttl)
        with self._lock:
            old = self._d.pop(key, None)
            if old:
                self._bytes -= old[2]
            self._d[key] = (ts, val, size)
            self._bytes += size
            while self._d and (
                len(self._d) > self.max_items
                or (self.max_bytes and self._bytes > self.max_bytes)
            ):
                _, (_, _, sz) = self._d.popitem(last=False)
                self._bytes -= sz

    def pop(self, key: Hashable) -> None:
        with self._lock:
            old = self._d.pop(key, None)
            if old:
                self._bytes -= old[2]


class SingleFlight:
    """Una sola ejecución por clave; el resto espera y recibe el mismo resultado."""

    def __init__(self):
        self._lock = threading.Lock()
        self._inflight: dict[Hashable, "_Call"] = {}

    def do(self, key: Hashable, fn: Callable[[], Any]) -> Any:
        with self._lock:
            call = self._inflight.get(key)
            leader = call is None
            if leader:
                call = _Call()
                self._inflight[key] = call
        if not leader:
            call.event.wait()
            if call.exc is not None:
                raise call.exc
            return call.value
        try:
            call.value = fn()
            return call.value
        except BaseException as exc:  # noqa: BLE001
            call.exc = exc
            raise
        finally:
            call.event.set()
            with self._lock:
                self._inflight.pop(key, None)


class _Call:
    __slots__ = ("event", "value", "exc")

    def __init__(self):
        self.event = threading.Event()
        self.value = None
        self.exc = None


# ── Resolución de streams compartida ─────────────────────────────

_RESOLVE_OK_TTL = 240
_RESOLVE_FAIL_TTL = 15

_resolve_cache = TTLCache(ttl=_RESOLVE_OK_TTL, max_items=128)
_resolve_flight = SingleFlight()


def resolve_cached(key: Hashable, fn: Callable[[], dict]) -> dict:
    hit = _resolve_cache.get(key)
    if hit is not None:
        return dict(hit)

    def _work() -> dict:
        again = _resolve_cache.get(key)
        if again is not None:
            return again
        data = fn()
        ok = bool(data.get("stream_url")) and not data.get("error")
        _resolve_cache.set(
            key, data, ttl=_RESOLVE_OK_TTL if ok else _RESOLVE_FAIL_TTL
        )
        return data

    return dict(_resolve_flight.do(key, _work))


def invalidate_resolve(key: Hashable) -> None:
    _resolve_cache.pop(key)


def _normalize_source(source: str) -> str:
    from modules.providers.registry import normalize_source

    return normalize_source(source)


def resolve_stream(
    source: str,
    content_type: str,
    content_id: str,
    season: int = 1,
    episode: int = 1,
    refresh: bool = False,
    alt_id: str | None = None,
) -> dict:
    """
    Punto único para resolver un stream (API y prewarm del bot).

    Delega en modules.providers.registry (cadenas por idioma).
    """
    from modules.providers.registry import lang_from_source, resolve_with_chain

    requested = _normalize_source(source)
    lang = lang_from_source(source)
    is_tv = (content_type or "").lower() in ("tv", "anime", "serie")
    cid = str(content_id)
    season_i, episode_i = int(season), int(episode)
    key = (
        lang,
        requested,
        "tv" if is_tv else "movie",
        cid,
        season_i if is_tv else 0,
        episode_i if is_tv else 0,
    )

    if refresh:
        invalidate_resolve(key)

    def _work() -> dict:
        return resolve_with_chain(
            lang=lang,
            content_type=content_type,
            content_id=cid,
            season=season_i,
            episode=episode_i,
            prefer=requested if requested in ("playlatinsrc", "vidsrc", "unlimplay", "videoapi", "vaplayer", "vidlink") else None,
            alt_id=alt_id,
        )

    return resolve_cached(key, _work)


# ── Resolución asíncrona (polling) ───────────────────────────────

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as _FutTimeout

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="resolve")
_jobs: dict = {}
_jobs_lock = threading.Lock()


def resolve_stream_wait(
    source: str,
    content_type: str,
    content_id: str,
    season: int = 1,
    episode: int = 1,
    refresh: bool = False,
    alt_id: str | None = None,
    wait: float = 2.5,
) -> Optional[dict]:
    is_tv = (content_type or "").lower() in ("tv", "anime", "serie")
    from modules.providers.registry import lang_from_source

    jkey = (
        lang_from_source(source),
        is_tv,
        str(content_id),
        int(season) if is_tv else 0,
        int(episode) if is_tv else 0,
    )
    created = False
    with _jobs_lock:
        fut = _jobs.get(jkey)
        if fut is None:
            fut = _executor.submit(
                resolve_stream,
                source,
                content_type,
                content_id,
                season,
                episode,
                refresh,
                alt_id,
            )
            _jobs[jkey] = fut
            created = True
    if created:

        def _cleanup(_f, _k=jkey):
            with _jobs_lock:
                if _jobs.get(_k) is _f:
                    _jobs.pop(_k, None)

        fut.add_done_callback(_cleanup)
    try:
        return dict(fut.result(timeout=wait))
    except _FutTimeout:
        return None
    except Exception as exc:  # noqa: BLE001
        print(f"[resolve] job falló: {exc}")
        return {"stream_url": None, "candidates": [], "error": "resolve_failed"}