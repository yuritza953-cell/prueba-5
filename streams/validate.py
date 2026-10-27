"""
Validación de streams antes de devolverlos al player.

- Manifiesto HLS debe empezar por #EXTM3U
- Descarta señuelos (1–2 segmentos muy cortos)
- MP4: HEAD/Range bytes=0-1 debe responder 200/206
"""
from __future__ import annotations

import re
from typing import Optional, Tuple
from urllib.parse import urljoin, urlparse

from streams.http_client import browser_headers, get

# Errores tipados
ERR_DEAD = "dead_file"
ERR_DECOY = "decoy_playlist"
ERR_NOT_M3U = "not_m3u8"
ERR_BLOCKED = "ProviderBlocked"
ERR_DOWN = "ProviderDown"
ERR_TIMEOUT = "ProviderDown"
ERR_NO_CORS_HINT = "needs_proxy"  # informativo


def _ref_headers(ref: str) -> dict:
    h = browser_headers(Accept="*/*")
    if ref:
        h["Referer"] = ref
        try:
            p = urlparse(ref)
            h["Origin"] = f"{p.scheme}://{p.netloc}"
        except Exception:
            pass
    return h



# Hosts / URLs que NUNCA son contenido real (demos de CDN, placeholders)
_BAD_STREAM_MARKERS = (
    "test-streams.mux.dev",
    "mux.dev/x36",
    "teststream",
    "example.com",
    "example.org",
    "example.net",
    "placeholder",
    "about:blank",
    "127.0.0.1",
    "localhost",
    "0.0.0.0",
)


def is_bad_stream_url(url: str) -> bool:
    u = (url or "").lower()
    if not u.startswith("https://"):
        return True
    return any(m in u for m in _BAD_STREAM_MARKERS)


def validate_stream(
    url: str,
    *,
    stream_type: str = "hls",
    ref: str = "",
    timeout: float = 6,
) -> Tuple[bool, Optional[str]]:
    """
    Realiza probe de verificación real (2 bytes) antes de devolver la URL al front.
    Returns (ok, error_code).
    """
    if not url or not url.startswith("https://"):
        return False, ERR_DEAD
    if is_bad_stream_url(url):
        return False, ERR_DECOY

    st = (stream_type or "hls").lower()
    headers = _ref_headers(ref)

    try:
        if st == "mp4" or url.lower().split("?")[0].endswith(".mp4"):
            return _validate_mp4(url, headers, timeout)
        return _validate_hls(url, headers, timeout, ref)
    except Exception as exc:
        msg = str(exc).lower()
        if "timed out" in msg or "timeout" in msg:
            return False, ERR_DOWN
        if "403" in msg or "cloudflare" in msg or "just a moment" in msg:
            return False, ERR_BLOCKED
        return False, ERR_DEAD


def _probe_bytes(url: str, headers: dict, timeout: float) -> Tuple[bool, Optional[str]]:
    """Probe real GET con Range: bytes=0-1 (nunca HEAD ni regex)."""
    hdrs = dict(headers)
    hdrs["Range"] = "bytes=0-1"
    try:
        r = get(url, headers=hdrs, timeout=timeout)
        code = getattr(r, "status_code", 0)
        if code in (200, 206):
            data = getattr(r, "content", b"")
            if not data and hasattr(r, "raw"):
                try:
                    data = r.raw.read(2)
                except Exception:
                    pass
            if data or code in (200, 206):
                return True, None
        if code in (401, 403, 429):
            return False, ERR_BLOCKED
        if code >= 500:
            return False, ERR_DOWN
        return False, ERR_DEAD
    except Exception as exc:
        msg = str(exc).lower()
        if "timeout" in msg or "timed out" in msg:
            return False, ERR_DOWN
        return False, ERR_DEAD


def _validate_mp4(url: str, headers: dict, timeout: float) -> Tuple[bool, Optional[str]]:
    return _probe_bytes(url, headers, timeout)


def _validate_hls(
    url: str, headers: dict, timeout: float, ref: str
) -> Tuple[bool, Optional[str]]:
    try:
        r = get(url, headers=headers, timeout=timeout)
    except Exception as exc:
        msg = str(exc).lower()
        if "timeout" in msg or "timed out" in msg:
            return False, ERR_DOWN
        return False, ERR_DEAD

    code = getattr(r, "status_code", 0)
    text = (getattr(r, "text", None) or "")[:8000]
    if code in (401, 403, 429) or "just a moment" in text.lower() or "cf-browser" in text.lower():
        return False, ERR_BLOCKED
    if code >= 500:
        return False, ERR_DOWN
    if code >= 400:
        return False, ERR_DEAD
    if not text.lstrip().startswith("#EXTM3U"):
        return False, ERR_NOT_M3U

    # Señuelo: muy pocos EXTINF y duraciones tiny
    durations = [float(m) for m in re.findall(r"#EXTINF:([\d.]+)", text)]
    if durations and len(durations) <= 2 and sum(durations) < 12:
        return False, ERR_DECOY

    # Probe real del primer segmento o variante (Range: bytes=0-1) para evitar 403 en CDN
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            seg_url = urljoin(url, line)
            probe_ok, probe_err = _probe_bytes(seg_url, headers, timeout)
            if not probe_ok and probe_err in (ERR_BLOCKED, ERR_DOWN):
                return False, probe_err
            break

    return True, None