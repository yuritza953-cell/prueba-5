"""
Firmas HMAC para URLs del Cloudflare Worker (proxy HLS de respaldo).

El backend firma; el Worker verifica. Render nunca sirve bytes de video.
Formato de query (compatible con el worker nuevo):

    ?u=<base64url URL> &e=<unix_exp> &s=<mac16> [&r=<base64url referer>]

Clave: STREAM_SIGN_KEY (env). Si no existe, se genera una efímera en arranque
(solo útil en local; en producción debe ser fija y compartida con el Worker).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
from typing import Optional, Tuple
from urllib.parse import urlencode

_SIGN_TTL = int(os.environ.get("STREAM_SIGN_TTL", "21600"))  # 2h default
_KEY_RAW = (os.environ.get("STREAM_SIGN_KEY") or "").strip()
if not _KEY_RAW:
    _KEY_RAW = secrets.token_hex(32)
_SIGN_KEY = _KEY_RAW.encode("utf-8") if isinstance(_KEY_RAW, str) else _KEY_RAW


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode((s + "=" * (-len(s) % 4)).encode("ascii"))


def _mac(url: str, ref: str, exp: int) -> str:
    msg = f"{exp}\n{ref}\n{url}".encode("utf-8")
    return _b64e(hmac.new(_SIGN_KEY, msg, hashlib.sha256).digest()[:16])


def signed_query(url: str, ref: str = "", ttl: int = _SIGN_TTL) -> str:
    """Query string firmada (sin path)."""
    exp = int(time.time()) + max(60, ttl)
    parts = {
        "u": _b64e(url.encode("utf-8")),
        "e": str(exp),
        "s": _mac(url, ref or "", exp),
    }
    if ref:
        parts["r"] = _b64e(ref.encode("utf-8"))
    return urlencode(parts)


# CDNs que amarran el token a la IP que resolvió (Render).
# El Worker de Cloudflare usa otra IP → 403 nginx. Mejor proxy local same-origin.
_LOCAL_PROXY_SUFFIXES = (
    "vimeos.net",
    "vimeos.zip",
)


def _needs_local_proxy(stream_url: str) -> bool:
    try:
        from urllib.parse import urlparse
        host = (urlparse(stream_url).hostname or "").lower()
    except Exception:
        return False
    for suf in _LOCAL_PROXY_SUFFIXES:
        if host == suf or host.endswith("." + suf):
            return True
    return False


def proxy_url(stream_url: str, *, ref: str = "", worker_base: str = "") -> str:
    """
    URL del proxy HLS para el player.

    - Hosts IP-bound (vimeos, etc.): siempre /api/hls relativo (Render, misma IP
      que resolvió el token).
    - Resto: Worker de Cloudflare si STREAM_WORKER_BASE está definido.
    - Sin worker: path relativo /api/hls?...
    """
    q = signed_query(stream_url, ref=ref)
    path = f"/api/hls?{q}"
    if _needs_local_proxy(stream_url):
        return path  # same-origin → Render
    base = (worker_base or "").rstrip("/")
    return f"{base}{path}" if base else path


def verify_signed(args: dict) -> Tuple[Optional[Tuple[str, str]], str]:
    """
    Verifica firma. Útil si el backend también expone un endpoint de diagnóstico.
    Returns: ((url, ref), "ok") | (None, reason)
    """
    try:
        url = _b64d(args.get("u", "")).decode("utf-8")
        ref = _b64d(args["r"]).decode("utf-8") if args.get("r") else ""
        exp = int(args.get("e", "0"))
        sig = args.get("s", "")
    except Exception:
        return None, "malformed"
    if exp < time.time():
        return None, "expired"
    if not hmac.compare_digest(sig, _mac(url, ref, exp)):
        return None, "bad_signature"
    return (url, ref), "ok"


def play_url(
    *,
    tmdb_id: str,
    media: str = "movie",
    season: int = 1,
    episode: int = 1,
    worker_base: str = "",
    ttl: int = _SIGN_TTL,
) -> str:
    """
    URL al Worker /api/play: resuelve + sirve el HLS con la IP del Worker.
    Firma: HMAC(exp + "\n" + "" + "\n" + "play:{media}:{id}:s{season}e{episode}")
    """
    media = "tv" if (media or "").lower() in ("tv", "serie", "series", "anime") else "movie"
    payload = f"play:{media}:{tmdb_id}:s{int(season)}e{int(episode)}"
    exp = int(time.time()) + max(60, ttl)
    parts = {
        "id": str(tmdb_id),
        "media": media,
        "season": str(int(season)),
        "episode": str(int(episode)),
        "e": str(exp),
        "s": _mac(payload, "", exp),
    }
    q = urlencode(parts)
    base = (worker_base or "").rstrip("/")
    path = f"/api/play?{q}"
    return f"{base}{path}" if base else path