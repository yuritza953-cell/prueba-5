"""
Orquestador híbrido de streams.

1. Cadena de providers (paralela, con validación).
2. direct=True solo si el host está en allowlist (no por token).
3. Hosts que exigen Referer → siempre proxy (direct=False).
4. Caché corta por (id, media, lang).
5. Sin fallback automático entre idiomas de audio.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from streams.signing import proxy_url
from streams.validate import validate_stream

try:
    from streams.registry import resolve_with_chain
except Exception as _e:  # noqa: BLE001
    raise RuntimeError(f"No se pudo importar resolve_with_chain: {_e}") from _e

try:
    from streams.registry import AUDIO_LANGS, normalize_audio_lang
except Exception:
    # Registry sin Fase 3 todavía: no tumbar /api/stream
    AUDIO_LANGS = [
        {"code": "es-MX", "label_es": "Español (Latino)", "label_en": "Spanish (Latin)"},
        {"code": "es-ES", "label_es": "Español (Castellano)", "label_en": "Spanish (Spain)"},
        {"code": "en", "label_es": "English", "label_en": "English"},
        {"code": "fr", "label_es": "Français", "label_en": "French"},
        {"code": "pt-BR", "label_es": "Português (Brasil)", "label_en": "Portuguese (Brazil)"},
    ]

    def normalize_audio_lang(lang):  # type: ignore
        s = (lang or "es-MX").strip().lower().replace("_", "-")
        if s.startswith("en"):
            return "en"
        if s in ("es-es", "castellano"):
            return "es-ES"
        if s.startswith("fr"):
            return "fr"
        if s.startswith("pt"):
            return "pt-BR"
        # Cadena legacy solo conoce "es" | "en"
        return "es"

_DEFAULT_DIRECT = (
    "vimeos.net",
    "vimeos.zip",
)

_REFERER_REQUIRED = (
    "voe.sx",
    "voe-unblock",
    "vidhide",
    "vidhidepro",
    "streamwish",
    "streamtape",
    "dood",
    "doodstream",
    "mixdrop",
    "mxcontent.net",
    "mxdrop",
    "filemoon",
    "luluvdo",
    "netu",
    "hqq",
)

_WORKER_BASE = (os.environ.get("STREAM_WORKER_BASE") or "").rstrip("/")
_SIGN_TTL = int(os.environ.get("STREAM_SIGN_TTL", "7200"))
_CACHE_TTL = int(os.environ.get("STREAM_CACHE_TTL", "1200"))  # 15–30 min para links (caducan)

_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_cache_lock = threading.Lock()

# Mapeo 24h (media, id) → provider ganador
_PROVIDER_MAP: Dict[Tuple[str, str], Tuple[float, str]] = {}
_PROVIDER_MAP_LOCK = threading.Lock()
_PROVIDER_MAP_TTL = 86400  # 24 horas


_MAX_PROVIDER_MAP_SIZE = 2000


def _get_mapped_provider(media: str, cid: str) -> Optional[str]:
    with _PROVIDER_MAP_LOCK:
        hit = _PROVIDER_MAP.get((media, cid))
        if not hit:
            return None
        exp, prov = hit
        if time.time() > exp:
            _PROVIDER_MAP.pop((media, cid), None)
            return None
        return prov


def _set_mapped_provider(media: str, cid: str, prov: str) -> None:
    if not prov:
        return
    with _PROVIDER_MAP_LOCK:
        if len(_PROVIDER_MAP) >= _MAX_PROVIDER_MAP_SIZE:
            to_del = list(_PROVIDER_MAP.keys())[: max(1, _MAX_PROVIDER_MAP_SIZE // 5)]
            for k in to_del:
                _PROVIDER_MAP.pop(k, None)
        _PROVIDER_MAP[(media, cid)] = (time.time() + _PROVIDER_MAP_TTL, prov)


def _direct_suffixes() -> tuple:
    extra = (os.environ.get("DIRECT_HOST_SUFFIXES") or "").strip()
    parts = [p.strip().lower() for p in extra.split(",") if p.strip()]
    return tuple(_DEFAULT_DIRECT) + tuple(parts)


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def _is_direct_host(url: str) -> bool:
    h = _host(url)
    if not h:
        return False
    for suf in _direct_suffixes():
        if h == suf or h.endswith("." + suf):
            return True
    return False


def _needs_referer_proxy(url: str) -> bool:
    h = _host(url)
    return any(x in h for x in _REFERER_REQUIRED)


def _annotate(
    url: str,
    stream_type: Optional[str],
    ref: str,
    *,
    force_proxy: bool = False,
) -> Dict[str, Any]:
    low = (url or "").lower()
    st = stream_type or ("mp4" if low.split("?")[0].endswith(".mp4") else "hls")
    host = _host(url)
    # Proxy local para vimeos (token atado a IP) y hosts que exigen Referer
    need_proxy = (
        force_proxy
        or _needs_referer_proxy(url)
        or "vimeos" in host
        or not _is_direct_host(url)
    )
    # allowlist directa solo si no necesita proxy
    direct = (not need_proxy) and _is_direct_host(url)
    item: Dict[str, Any] = {
        "url": url,
        "type": st,
        "direct": bool(direct),
        "ref": ref or "",
    }
    if not direct:
        try:
            item["proxy_url"] = proxy_url(url, ref=ref or "", worker_base=_WORKER_BASE)
        except Exception as exc:
            print(f"[stream] proxy_url fail: {exc}")
            item["proxy_url"] = f"/api/hls?u=error"
    else:
        item["proxy_url"] = None
    return item


def _cache_key(media: str, cid: str, lang: str, season: int, episode: int) -> str:
    return f"{media}|{cid}|{lang}|{season}|{episode}"


def _cache_get(key: str) -> Optional[Dict[str, Any]]:
    with _cache_lock:
        hit = _cache.get(key)
        if not hit:
            return None
        exp, payload = hit
        if time.time() > exp:
            _cache.pop(key, None)
            return None
        return dict(payload)


_MAX_CACHE_SIZE = 1000


def _cache_set(key: str, payload: Dict[str, Any]) -> None:
    with _cache_lock:
        if len(_cache) >= _MAX_CACHE_SIZE:
            to_del = list(_cache.keys())[: max(1, _MAX_CACHE_SIZE // 5)]
            for k in to_del:
                _cache.pop(k, None)
        _cache[key] = (time.time() + _CACHE_TTL, dict(payload))


def _cache_clear() -> None:
    with _cache_lock:
        _cache.clear()


def resolve_stream(
    *,
    media: str,
    tmdb_id: str,
    lang: str = "es-MX",
    season: int = 1,
    episode: int = 1,
    imdb_id: Optional[str] = None,
    prefer: Optional[str] = None,
    force_proxy: bool = False,
    skip_cache: bool = False,
) -> Dict[str, Any]:
    media = "tv" if (media or "").lower() in ("tv", "serie", "series", "anime") else "movie"
    lang = normalize_audio_lang(lang)

    # Qué clave usar en CHAINS del registry (nuevo o legacy)
    chain_lang = lang
    try:
        from streams.registry import CHAINS as _CHAINS

        if lang in _CHAINS:
            chain_lang = lang
        elif lang.startswith("es") and "es-MX" in _CHAINS:
            chain_lang = "es-MX" if lang != "es-ES" else ("es-ES" if "es-ES" in _CHAINS else "es-MX")
        elif lang.startswith("es") and "es" in _CHAINS:
            chain_lang = "es"
        elif lang == "en" and "en" in _CHAINS:
            chain_lang = "en"
        elif lang.startswith("fr"):
            chain_lang = "fr" if "fr" in _CHAINS else "en"
        elif lang.startswith("pt"):
            chain_lang = "pt-BR" if "pt-BR" in _CHAINS else ("pt" if "pt" in _CHAINS else "es")
        else:
            chain_lang = "es" if "es" in _CHAINS else next(iter(_CHAINS), "es")
    except Exception:
        chain_lang = "en" if str(lang).startswith("en") else "es"

    print(
        f"[stream] resolve media={media} id={tmdb_id} lang={lang} chain_lang={chain_lang}",
        flush=True,
    )
    if (os.environ.get("STREAM_NO_CACHE") or "").lower() in ("1", "true", "yes"):
        _cache_clear()
    cid = str(tmdb_id or "").strip()
    if not cid:
        return {
            "ok": False,
            "error": "missing_tmdb_id",
            "error_class": "needs_id",
            "streams": [],
            "lang": lang,
            "available_langs": list(AUDIO_LANGS),
        }

    # Sanitizar prefer contra providers conocidos para evitar bypass arbitrario de caché
    valid_prefer = None
    if prefer:
        try:
            from streams.registry import _builtin
            if prefer.lower().strip() in _builtin():
                valid_prefer = prefer.lower().strip()
        except Exception:
            pass

    effective_prefer = valid_prefer or _get_mapped_provider(media, cid)

    ck = _cache_key(media, cid, lang, season, episode)
    if not skip_cache:
        cached = _cache_get(ck)
        if cached:
            # Si no se solicitó un provider preferido o si el provider cacheado coincide con prefer
            if not valid_prefer or cached.get("provider") == valid_prefer:
                cached["cached"] = True
                cached.setdefault("available_langs", list(AUDIO_LANGS))
                return cached

    try:
        raw = resolve_with_chain(
            lang=chain_lang,
            content_type=media,
            content_id=cid,
            season=season,
            episode=episode,
            prefer=effective_prefer,
            alt_id=imdb_id,
        )
    except Exception as exc:  # noqa: BLE001
        import traceback

        print(f"[stream] resolve_with_chain EXCEPTION: {type(exc).__name__}: {exc}", flush=True)
        traceback.print_exc()
        raw = {
            "stream_url": None,
            "candidates": [],
            "error": f"resolve_exception:{type(exc).__name__}:{exc}",
            "error_class": "resolve_exception",
            "provider": None,
            "tried": [],
            "ref_url": "",
            "stream_type": None,
            "lang": chain_lang,
        }

    print(
        f"[stream] chain done provider={raw.get('provider')} err={raw.get('error')} "
        f"url={'yes' if raw.get('stream_url') else 'no'} "
        f"cands={len(raw.get('candidates') or [])} tried={len(raw.get('tried') or [])}",
        flush=True,
    )
    if raw.get("tried"):
        print(
            "[stream] tried "
            + ", ".join(f"{x.get('source')}:{x.get('error')}" for x in raw["tried"][:12]),
            flush=True,
        )


    # Fallback opcional solo si STREAM_LANG_FALLBACK=1 o "on" (por defecto off).
    # El player pide un idioma concreto; no mezclar audio sin que el usuario lo sepa.
    if not raw.get("stream_url") and not (raw.get("candidates") or []):
        fb = (os.environ.get("STREAM_LANG_FALLBACK") or "off").lower()
        allow = fb in ("1", "true", "yes", "on")
        if allow:
            other = None
            if str(lang).startswith("es"):
                other = "en"
            elif lang == "en":
                other = "es-MX"
            if other:
                print(f"[stream] fallback chain lang={other} (STREAM_LANG_FALLBACK={fb})", flush=True)
                try:
                    raw2 = resolve_with_chain(
                        lang=other,
                        content_type=media,
                        content_id=cid,
                        season=season,
                        episode=episode,
                        prefer=effective_prefer,
                        alt_id=imdb_id,
                    )
                    if raw2.get("stream_url") or (raw2.get("candidates") or []):
                        raw = raw2
                        raw["lang"] = other
                        raw["lang_fallback"] = True
                        raw["requested_lang"] = lang
                except Exception as fb_exc:
                    print(f"[stream] fallback chain exception: {fb_exc}", flush=True)


    streams: List[Dict[str, Any]] = []
    ref = raw.get("ref_url") or ""
    stype = raw.get("stream_type")
    seen = set()

    candidates = list(raw.get("candidates") or [])
    if raw.get("stream_url") and raw["stream_url"] not in candidates:
        candidates.insert(0, raw["stream_url"])

    for url in candidates:
        if not url or url in seen:
            continue
        seen.add(url)
        ok, verr = validate_stream(url, stream_type=stype or "hls", ref=ref)
        if not ok:
            print(f"[stream] discard probe fail {verr} {url[:70]}")
            continue
        streams.append(_annotate(url, stype, ref, force_proxy=force_proxy))

    tried = raw.get("tried") or []
    err = None if streams else (raw.get("error") or "no_stream_for_lang")
    err_class = None if streams else (raw.get("error_class") or "no_stream_for_lang")
    payload: Dict[str, Any] = {
        "ok": bool(streams),
        "lang": raw.get("lang") or lang,
        "available_langs": list(AUDIO_LANGS),
        "provider": raw.get("provider"),
        "stream_type": stype or (streams[0]["type"] if streams else None),
        "streams": streams,
        "expires_in": _SIGN_TTL,
        "ref_url": ref,
        "error": err,
        "error_class": err_class,
        "error_lang": None if streams else lang,
        "lang_fallback": bool(raw.get("lang_fallback")),
        "tried": tried,
        "worker_base": _WORKER_BASE or None,
        "cached": False,
    }

    if streams:
        if raw.get("provider"):
            _set_mapped_provider(media, cid, raw["provider"])
        if not prefer:
            _cache_set(ck, payload)

    return payload