"""
OpenSubtitles.com REST API — búsqueda y descarga de subtítulos.

Env:
  OPENSUBTITLES_API_KEY  (obligatoria)
  OPENSUBTITLES_USER_AGENT  default "Kinora v1.0"
  OPENSUBTITLES_USERNAME / OPENSUBTITLES_PASSWORD  (opcionales, más cuota)
"""
from __future__ import annotations

import os
import re
import threading
import time
from typing import Any, Dict, List, Optional

import requests

_API = "https://api.opensubtitles.com/api/v1"

_token: Optional[str] = None
_token_exp = 0.0

# Caché en memoria para evitar agotar cuota de OpenSubtitles
_SUB_CACHE: Dict[int, Dict[str, Any]] = {}
_SUB_CACHE_LOCK = threading.Lock()
_MAX_SUB_CACHE = 500

# Rate limit de descargas: max 15 por minuto
_DL_TIMESTAMPS: List[float] = []
_DL_LIMIT_LOCK = threading.Lock()
_MAX_DL_PER_MINUTE = 15


def _cfg():
    """Lee env en cada uso (load_env del server corre después del import)."""
    return {
        "key": (os.environ.get("OPENSUBTITLES_API_KEY") or "").strip(),
        "ua": (os.environ.get("OPENSUBTITLES_USER_AGENT") or "Kinora v1.0").strip(),
        "user": (os.environ.get("OPENSUBTITLES_USERNAME") or "").strip(),
        "password": (os.environ.get("OPENSUBTITLES_PASSWORD") or "").strip(),
    }

# Idiomas prioritarios para el selector (ISO 639-1 / variantes OS)
LANG_OPTIONS = [
    ("es", "Español"),
    ("es-MX", "Español (Latino)"),
    ("es-ES", "Español (España)"),
    ("en", "English"),
    ("pt-BR", "Português (Brasil)"),
    ("pt-PT", "Português"),
    ("fr", "Français"),
    ("it", "Italiano"),
    ("de", "Deutsch"),
    ("ja", "日本語"),
    ("ko", "한국어"),
    ("zh-CN", "中文"),
    ("zh-TW", "繁體中文"),
    ("ar", "العربية"),
    ("ru", "Русский"),
    ("hi", "हिन्दी"),
    ("tr", "Türkçe"),
    ("pl", "Polski"),
    ("nl", "Nederlands"),
    ("sv", "Svenska"),
]


def _headers(auth: bool = False) -> Dict[str, str]:
    c = _cfg()
    h = {
        "Api-Key": c["key"],
        "User-Agent": c["ua"],
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if auth and _token:
        h["Authorization"] = f"Bearer {_token}"
    return h


def _ensure_login() -> None:
    global _token, _token_exp
    c = _cfg()
    if not c["user"] or not c["password"]:
        return
    if _token and time.time() < _token_exp - 60:
        return
    try:
        r = requests.post(
            f"{_API}/login",
            headers=_headers(),
            json={"username": c["user"], "password": c["password"]},
            timeout=20,
        )
        if r.status_code >= 400:
            print(f"[subs] login fail {r.status_code}: {r.text[:120]}")
            return
        data = r.json()
        _token = data.get("token") or data.get("jwt") or None
        # tokens suelen durar ~24h; refrescamos a las 20h
        _token_exp = time.time() + 20 * 3600
        print("[subs] login ok")
    except Exception as exc:
        print(f"[subs] login error: {exc}")


def _norm_imdb(imdb: Optional[str]) -> Optional[str]:
    if not imdb:
        return None
    s = str(imdb).strip()
    if s.startswith("tt"):
        s = s[2:]
    s = s.lstrip("0") or "0"
    return s if s.isdigit() else None


def search_subs(
    *,
    tmdb_id: Optional[str] = None,
    imdb_id: Optional[str] = None,
    media: str = "movie",
    season: Optional[int] = None,
    episode: Optional[int] = None,
    languages: str = "es,en",
    page: int = 1,
) -> Dict[str, Any]:
    if not _cfg()["key"]:
        return {"ok": False, "error": "missing_opensubtitles_api_key", "subs": []}

    _ensure_login()
    params: Dict[str, Any] = {
        "languages": languages.replace(" ", ""),
        "order_by": "download_count",
        "order_direction": "desc",
        "page": page,
    }
    mid = _norm_imdb(imdb_id)
    if mid:
        params["imdb_id"] = mid
    if tmdb_id and str(tmdb_id).isdigit():
        params["tmdb_id"] = int(tmdb_id)

    is_tv = (media or "").lower() in ("tv", "serie", "series", "anime")
    if is_tv:
        params["type"] = "episode"
        if season is not None:
            params["season_number"] = int(season)
        if episode is not None:
            params["episode_number"] = int(episode)
    else:
        params["type"] = "movie"

    try:
        r = requests.get(
            f"{_API}/subtitles",
            headers=_headers(auth=True),
            params=params,
            timeout=25,
        )
        if r.status_code == 401 and _cfg()["user"]:
            # token viejo
            global _token
            _token = None
            _ensure_login()
            r = requests.get(
                f"{_API}/subtitles",
                headers=_headers(auth=True),
                params=params,
                timeout=25,
            )
        if r.status_code >= 400:
            return {
                "ok": False,
                "error": f"os_http_{r.status_code}",
                "detail": r.text[:200],
                "subs": [],
            }
        data = r.json()
    except Exception as exc:
        return {"ok": False, "error": f"os_request:{exc}", "subs": []}

    out: List[Dict[str, Any]] = []
    for item in data.get("data") or []:
        attrs = item.get("attributes") or {}
        files = attrs.get("files") or []
        if not files:
            continue
        f0 = files[0]
        lang = (attrs.get("language") or "").lower()
        out.append(
            {
                "id": str(item.get("id") or ""),
                "file_id": f0.get("file_id"),
                "file_name": f0.get("file_name") or attrs.get("release") or "",
                "language": lang,
                "label": _lang_label(lang),
                "downloads": attrs.get("download_count") or 0,
                "hearing_impaired": bool(attrs.get("hearing_impaired")),
                "ai_translated": bool(attrs.get("ai_translated")),
                "machine_translated": bool(attrs.get("machine_translated")),
                "fps": attrs.get("fps"),
                "release": attrs.get("release") or "",
            }
        )

    # dedupe por language+file_id, orden por downloads
    seen = set()
    unique = []
    for s in sorted(out, key=lambda x: -x["downloads"]):
        k = (s["language"], s["file_id"])
        if k in seen or not s["file_id"]:
            continue
        seen.add(k)
        unique.append(s)

    return {
        "ok": True,
        "subs": unique[:40],
        "total": data.get("total_count"),
        "languages": LANG_OPTIONS,
    }


def download_sub(file_id: int) -> Dict[str, Any]:
    """Pide link de descarga a OS y devuelve el contenido en VTT (texto). Protegido con caché y rate limit."""
    if not file_id:
        return {"ok": False, "error": "missing_file_id"}

    try:
        fid = int(file_id)
    except (TypeError, ValueError):
        return {"ok": False, "error": "invalid_file_id"}

    # 1. Chequeo de caché en memoria (ahorra cuota de descarga y sirve inmediato)
    with _SUB_CACHE_LOCK:
        hit = _SUB_CACHE.get(fid)
        if hit:
            return dict(hit)

    if not _cfg()["key"]:
        return {"ok": False, "error": "missing_opensubtitles_api_key"}

    # 2. Rate limit: evitar agotar cuota por llamadas repetidas o bots
    with _DL_LIMIT_LOCK:
        now = time.time()
        _DL_TIMESTAMPS[:] = [t for t in _DL_TIMESTAMPS if now - t < 60]
        if len(_DL_TIMESTAMPS) >= _MAX_DL_PER_MINUTE:
            return {
                "ok": False,
                "error": "rate_limit_exceeded",
                "detail": "Demasiadas descargas de subtítulos por minuto. Por favor espera un momento.",
            }
        _DL_TIMESTAMPS.append(now)

    _ensure_login()
    try:
        r = requests.post(
            f"{_API}/download",
            headers=_headers(auth=True),
            json={"file_id": fid},
            timeout=25,
        )
        if r.status_code >= 400:
            return {"ok": False, "error": f"os_dl_{r.status_code}", "detail": r.text[:200]}
        info = r.json()
        link = info.get("link") or info.get("url")
        if not link:
            return {"ok": False, "error": "no_download_link", "raw": info}
        fr = requests.get(link, timeout=30, headers={"User-Agent": _cfg()["ua"]})
        if fr.status_code >= 400:
            return {"ok": False, "error": f"fetch_{fr.status_code}"}
        raw = fr.content
        # detectar encoding
        text = _decode_sub(raw)
        vtt = srt_to_vtt(text) if _looks_srt(text) else (
            text if text.lstrip().startswith("WEBVTT") else srt_to_vtt(text)
        )
        res = {
            "ok": True,
            "vtt": vtt,
            "remaining": info.get("remaining"),
            "file_name": info.get("file_name") or "",
        }
        with _SUB_CACHE_LOCK:
            if len(_SUB_CACHE) >= _MAX_SUB_CACHE:
                to_del = list(_SUB_CACHE.keys())[:50]
                for k in to_del:
                    _SUB_CACHE.pop(k, None)
            _SUB_CACHE[fid] = dict(res)
        return res
    except Exception as exc:
        return {"ok": False, "error": f"download:{exc}"}


def _lang_label(code: str) -> str:
    c = (code or "").lower()
    for k, lab in LANG_OPTIONS:
        if k.lower() == c or k.lower().startswith(c) or c.startswith(k.lower()[:2]):
            return lab
    return code.upper() if code else "Unknown"


def _decode_sub(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", errors="replace")


def _looks_srt(text: str) -> bool:
    t = text.lstrip()
    if t.startswith("WEBVTT"):
        return False
    return bool(re.search(r"\d+\s*\n\d{2}:\d{2}:\d{2}[,.]\d{3}\s*-->", t))


def srt_to_vtt(srt: str) -> str:
    """Convierte SRT a WebVTT básico."""
    body = srt.replace("\r\n", "\n").replace("\r", "\n").strip()
    if body.startswith("WEBVTT"):
        return body if body.endswith("\n") else body + "\n"
    # comas de milisegundos SRT → punto VTT
    body = re.sub(
        r"(\d{2}:\d{2}:\d{2}),(\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}),(\d{3})",
        r"\1.\2 --> \3.\4",
        body,
    )
    # quitar índices numéricos de bloque (línea sola con dígitos)
    lines = []
    for line in body.split("\n"):
        if re.fullmatch(r"\d+", line.strip()):
            continue
        lines.append(line)
    return "WEBVTT\n\n" + "\n".join(lines).strip() + "\n"