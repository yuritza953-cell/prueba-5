"""
UnlimPlay stream resolver (pulido).

Flujo:
    embed HTML
      → ULP_SESSION_TOKEN (HMAC ~5 min)
      → providers (finalizePlayer / URLs)
      → POST /f.php?_hlsextract=1  con header X-ULP-Token
      → streams HLS/MP4

No fabrica tokens. Solo usa el token que el propio embed publica.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FutTimeout

import json
import re
import threading
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote, unquote, urljoin, urlparse

import os
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from .constants import BASE_URL, EMBED_MOVIE, EMBED_TV, HTTP_TIMEOUT

# curl_cffi: mismo API que requests pero con JA3 de Chrome (evita CF en muchos casos).
# Si no está instalado, caemos a requests normal.
try:
    from curl_cffi import requests as _cffi_requests

    _HAS_CFFI = True
except Exception:
    _cffi_requests = None  # type: ignore
    _HAS_CFFI = False

# chrome131 / chrome124 / chrome120 — override con ULP_IMPERSONATE
_IMPERSONATE = (os.environ.get("ULP_IMPERSONATE") or "chrome131").strip()

# Proxies residenciales (mismo formato que keep_alive / hls_proxy):
#   PROXY_LIST=host:port:user:pass,...
# ULP_USE_PROXY=1 (default si hay PROXY_LIST) → embed pasa por proxy + JA3
_PROXY_IDX = 0


def _parse_proxy_list(raw: str):
    out = []
    if not raw:
        return out
    for line in raw.replace(";", ",").split(","):
        line = line.strip()
        if not line:
            continue
        if "://" in line or "@" in line:
            if not line.startswith("http"):
                line = "http://" + line
            out.append(line)
            continue
        parts = line.split(":")
        if len(parts) >= 4:
            host, port, user, passwd = parts[0], parts[1], parts[2], ":".join(parts[3:])
            out.append(
                "http://%s:%s@%s:%s"
                % (quote(user, safe=""), quote(passwd, safe=""), host, port)
            )
        elif len(parts) == 2:
            out.append("http://%s:%s" % (parts[0], parts[1]))
    return out


_PROXY_LIST = _parse_proxy_list(os.environ.get("PROXY_LIST") or "")
_ULP_USE_PROXY = (os.environ.get("ULP_USE_PROXY") or ("1" if _PROXY_LIST else "0")).lower() not in (
    "0",
    "false",
    "no",
)


def _next_ulp_proxy() -> dict | None:
    """Dict proxies= para curl_cffi/requests, o None = directo."""
    global _PROXY_IDX
    if not _ULP_USE_PROXY or not _PROXY_LIST:
        return None
    u = _PROXY_LIST[_PROXY_IDX % len(_PROXY_LIST)]
    _PROXY_IDX += 1
    return {"http": u, "https": u}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

HLS_EXTRACT_URL = BASE_URL.rstrip("/") + "/f.php?_hlsextract=1"

_CDN_HOSTS = {
    "unlimplay.com",
    "www.unlimplay.com",
    "vimeos.unlimplay.com",
    "sololatino.unlimplay.com",
}

# Headers de navegador real (CF bloquea UA viejos / sin Sec-Fetch-*)
_BROWSER_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate",  # sin br: requests no descomprime brotli sin paquete extra
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Upgrade-Insecure-Requests": "1",
}

# Sesión POR HILO: antes era global y _reset_session() borraba las cookies
# mientras otra resolución estaba a medias (race condition con 2+ usuarios).
_TLS = threading.local()


def _new_session():
    """Session por hilo: curl_cffi (Chrome JA3) si está, si no requests.

    Si hay PROXY_LIST y ULP_USE_PROXY, fija UN proxy por sesión (sticky)
    para que warm + embed + hlsextract salgan por la misma IP.
    """
    proxy = _next_ulp_proxy()
    if _HAS_CFFI:
        s = _cffi_requests.Session(impersonate=_IMPERSONATE)
        s.headers.update(_BROWSER_HEADERS)
        s.warmed = False  # type: ignore[attr-defined]
        s.ulp_proxy = proxy  # type: ignore[attr-defined]
        via = "proxy" if proxy else "direct"
        s.client_name = f"curl_cffi/{_IMPERSONATE}/{via}"  # type: ignore[attr-defined]
        return s
    s = requests.Session()
    s.headers.update(_BROWSER_HEADERS)
    s.warmed = False  # type: ignore[attr-defined]
    s.ulp_proxy = proxy  # type: ignore[attr-defined]
    via = "proxy" if proxy else "direct"
    s.client_name = f"requests/{via}"  # type: ignore[attr-defined]
    return s


def _session_proxies():
    try:
        return getattr(_SESSION._s(), "ulp_proxy", None)
    except Exception:
        return None


class _SessionProxy:
    """Se usa igual que `requests.Session` (_SESSION.get/post/cookies)."""

    def _s(self):
        s = getattr(_TLS, "session", None)
        if s is None:
            s = _TLS.session = _new_session()
            # Log una sola vez por hilo
            if not getattr(_TLS, "client_logged", False):
                print(f"[UNLIMPLAY] http_client={getattr(s, 'client_name', '?')}")
                _TLS.client_logged = True
        return s

    def __getattr__(self, name):
        return getattr(self._s(), name)


_SESSION = _SessionProxy()


def _is_warm() -> bool:
    return bool(getattr(_SESSION._s(), "warmed", False))


def _set_warm(v: bool) -> None:
    _SESSION._s().warmed = v


def _client_name() -> str:
    try:
        return str(getattr(_SESSION._s(), "client_name", "unknown"))
    except Exception:
        return "unknown"


# (connect, read) — connect corto, read más generoso (CF a veces tarda)
_TIMEOUT_CONNECT = 8
_TIMEOUT_READ = max(min(HTTP_TIMEOUT, 12), 10)
_TIMEOUT = (_TIMEOUT_CONNECT, _TIMEOUT_READ)
_MAX_RETRIES = 1


def _warm_home(force: bool = False) -> None:
    """Visita la home para cookies CF. force=True renueva sesión completa."""
    if _is_warm() and not force:
        return
    try:
        if force:
            try:
                _SESSION.cookies.clear()
            except Exception:
                pass
            _set_warm(False)
        _SESSION.get(
            BASE_URL.rstrip("/") + "/",
            headers={
                **_BROWSER_HEADERS,
                "Referer": "https://www.google.com/",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "cross-site",
                "Sec-Fetch-User": "?1",
            },
            timeout=_TIMEOUT,
            allow_redirects=True,
            proxies=_session_proxies(),
        )
        _set_warm(True)
    except Exception as exc:
        print(f"[UNLIMPLAY] warm_home fail: {exc}")


def _reset_session() -> None:
    """Nueva sesión (nuevo JA3 + otro proxy del pool) y warm."""
    try:
        _TLS.session = None  # fuerza _new_session() con otro proxy
    except Exception:
        try:
            _SESSION.cookies.clear()
        except Exception:
            pass
        _set_warm(False)
    _warm_home(force=True)


# ── utils ────────────────────────────────────────────────────


def _unique(items: List[str]) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for x in items:
        if not x or x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def _host(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower().split(":")[0]
    except Exception:
        return ""


def _clean_url(url: str, base: Optional[str] = None) -> Optional[str]:
    if not url:
        return None
    url = str(url).strip().replace("\\/", "/").replace("&amp;", "&")
    url = url.strip("\"'` ")
    if base and not url.startswith(("http://", "https://")):
        url = urljoin(base, url)
    if not url.startswith(("http://", "https://")):
        return None
    return url


def _is_valid_stream(url: str) -> bool:
    if not url:
        return False
    low = url.lower()
    if re.search(r"[?&]url=(?:&|$)", low):
        return False
    return (
        ".m3u8" in low
        or ".mp4" in low
        or "master.txt" in low
        or "playlist.m3u8" in low
        or "stream.m3u8" in low
    )


def _priority(url: str) -> int:
    """Menor = mejor. vimeos.zip es el CDN que más suele funcionar con el proxy."""
    low = url.lower()
    score = 100
    # CDN preferido (probado en Discord Activity)
    if "vimeos.zip" in low or "vimeos.unlimplay.com" in low:
        score -= 60
    if "/stream/" in low and ".m3u8" in low:
        score -= 25
    if "master.m3u8" in low:
        score -= 20
    if ".m3u8" in low and "master.txt" not in low:
        score -= 15
    if "master.txt" in low:
        score -= 5
    if ".mp4" in low:
        score -= 8
    # CDNs que suelen 403 desde datacenter / bot
    if "morencius.com" in low:
        score += 25
    if "dramiyos-cdn" in low or "acek-cdn" in low:
        score += 15
    if "latestmusicchart" in low or "agilebusiness" in low:
        score += 20
    if "premilkyway.com" in low:
        score -= 52
    if "vibuxer.com" in low or "embedwish.com/stream" in low:
        score += 40
    if "viatrixfashionhouse" in low:
        score -= 20
    if "fastream.to" in low and ".m3u8" in low:
        score -= 48
    if "architectureguide.site" in low or "homeautomationkit.site" in low:
        score -= 42
    if "websitetrafficboost.site" in low:
        score -= 40
    # Captura 2026-10-12: quickcore MP4 + oakridge HLS estables
    if "quickcore.fun" in low:
        score -= 55
    if "oakridgedesigncollect.cyou" in low:
        score -= 58
    if ".woff2" in low and ("hls" in low or "seg-" in low):
        score -= 10
    return score


# ── fetch ────────────────────────────────────────────────────


class EmbedError(RuntimeError):
    """Fallo al obtener el embed, con un código estable para logs y UI."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


_CF_MARKERS = (
    "just a moment",
    "cf-chl",
    "challenge-platform",
    "attention required",
    "cf-browser-verification",
    "verificando",
    "checking your browser",
    "enable javascript and cookies",
    "cf-turnstile",
    "managed_checking",
)
_MISSING_MARKERS = ("no encontrado", "not found", "no disponible", "not available", "no existe", "sin resultados")


def _diagnose_embed(r: requests.Response) -> str:
    """Clasifica un embed 200 que no trae token/player y deja pistas en el log."""
    html = r.text or ""
    head = html[:6000]
    low = head.lower()
    m = re.search(r"<title[^>]*>(.*?)</title>", head, re.I | re.S)
    title = (m.group(1).strip()[:80] if m else "")
    if any(k in low for k in _CF_MARKERS):
        code = "embed_challenge"
    elif any(k in low for k in _MISSING_MARKERS) and len(html) < 20000:
        code = "embed_not_available"
    else:
        code = "embed_no_player"
    snippet = re.sub(r"\s+", " ", head[:160])
    print(
        f"[UNLIMPLAY] {code} status={r.status_code} final={(r.url or '')[:90]} "
        f"len={len(html)} title={title!r} head={snippet!r}"
    )
    return code


def _fetch_embed(embed_url: str) -> str:
    """
    Descarga el HTML del embed con reintentos.
    Lanza EmbedError(code):
      embed_blocked       403 / token expirado (se reintenta con sesión nueva)
      embed_challenge     desafío anti-bot (se reintenta)
      embed_not_available el título no existe en UnlimPlay (NO se reintenta)
      embed_no_player     200 sin token/player (se reintenta 1 vez)
      embed_timeout       red lenta o caída
    """
    headers = {
        **_BROWSER_HEADERS,
        "Referer": BASE_URL.rstrip("/") + "/",
        "Origin": BASE_URL.rstrip("/"),
        "Sec-Fetch-Dest": "iframe",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
    }

    last: EmbedError | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            if attempt == 1 or not _is_warm():
                _warm_home()

            r = _SESSION.get(
                embed_url,
                headers=headers,
                timeout=_TIMEOUT,
                allow_redirects=True,
                proxies=_session_proxies(),
            )

            body_head = (r.text or "")[:4000]
            blocked = (
                r.status_code == 403
                or "Acceso Bloqueado" in body_head
                or "ERR_TOKEN_EXPIRED" in body_head
                or "token de acceso" in body_head.lower()
                or "SESSION TOKEN" in body_head
                or "EXPIRADO" in body_head
            )
            if blocked:
                print(f"[UNLIMPLAY] embed bloqueado/token expirado (intento {attempt}/{_MAX_RETRIES})")
                _reset_session()
                last = EmbedError("embed_blocked", f"status={r.status_code}")
                time.sleep(0.6 * attempt)
                continue

            if r.status_code == 404:
                raise EmbedError("embed_not_available", "404")
            r.raise_for_status()

            text = r.text or ""
            if "ULP_SESSION_TOKEN" in text or "finalizePlayer" in text:
                print(
                    f"[UNLIMPLAY] embed OK client={_client_name()} "
                    f"len={len(text)} token={'ULP_SESSION_TOKEN' in text}"
                )
                return text

            code = _diagnose_embed(r)
            if code == "embed_not_available":
                raise EmbedError(code)  # reintentar no sirve: el título no está
            last = EmbedError(code)
            if code == "embed_no_player" and attempt >= 2:
                break  # dos intentos bastan; no gastes 4 s más
            if code == "embed_challenge":
                # Con curl_cffi a veces el 2º intento (cookies + JA3) pasa el challenge.
                # Con requests puro casi nunca: un solo reintento máximo.
                print(
                    f"[UNLIMPLAY] embed_challenge retry "
                    f"client={_client_name()} attempt={attempt}/{_MAX_RETRIES}"
                )
                if attempt >= (2 if _HAS_CFFI else 1):
                    raise EmbedError(code)
                _reset_session()
                time.sleep(0.7 * attempt)
                continue
            _reset_session()
            time.sleep(0.5 * attempt)

        except EmbedError:
            raise
        except (requests.Timeout, requests.ConnectionError) as exc:
            print(f"[UNLIMPLAY] embed timeout/conn (intento {attempt}/{_MAX_RETRIES}): {exc}")
            last = EmbedError("embed_timeout", str(exc)[:120])
            _set_warm(False)
            time.sleep(0.6 * attempt)
        except requests.HTTPError as exc:
            print(f"[UNLIMPLAY] embed http error: {exc}")
            last = EmbedError("embed_http_error", str(exc)[:120])
            break

    raise last or EmbedError("embed_fetch_error")


# ── token ────────────────────────────────────────────────────


def _extract_ulp_token(html: str) -> Optional[str]:
    """
    Token de sesión HMAC publicado por el embed (~5 min).
    Header real: X-ULP-Token
    """
    if not html:
        return None

    patterns = [
        r'ULP_SESSION_TOKEN\s*=\s*"([^"]+)"',
        r"ULP_SESSION_TOKEN\s*=\s*'([^']+)'",
        r'["\']x-ulp-token["\']\s*:\s*["\']([^"\']+)["\']',
        r'data-x-ulp-token\s*=\s*["\']([^"\']+)["\']',
    ]
    for pat in patterns:
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            tok = m.group(1).strip()
            if len(tok) > 16:
                return tok
    return None


# ── providers ────────────────────────────────────────────────


def _extract_from_finalize_player(html: str) -> List[str]:
    """Providers del mapa finalizePlayer({ latino: { voe: url, ... } })."""
    found: List[str] = []
    idx = html.find("finalizePlayer(")
    if idx < 0:
        return found
    i = html.find("{", idx)
    if i < 0:
        return found
    depth = 0
    end_i = -1
    for j in range(i, min(i + 80000, len(html))):
        ch = html[j]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end_i = j
                break
    if end_i < 0:
        return found
    blob = html[i : end_i + 1]
    for u in re.findall(r"https?://[^\"\s]+", blob):
        cleaned = _clean_url(u.replace(r"\/", "/"))
        if cleaned:
            found.append(cleaned)
    return _unique(found)


def _extract_provider_urls(html: str, embed_url: str) -> List[str]:
    found = _extract_from_finalize_player(html)

    for raw in re.findall(r"https?://[^\"'<>\\\s]+", html):
        url = _clean_url(raw, embed_url)
        if not url:
            continue
        host = _host(url)
        if not host or host in _CDN_HOSTS:
            continue
        path = urlparse(url).path.lower()
        like = (
            "/v/" in path
            or "/e/" in path
            or "/embed" in path
            or "/player/" in path
            or any(
                k in host
                for k in (
                    "voe", "wish", "filemoon", "morencius", "fastream", "dood",
                    "vibuxer", "streamhg", "filelions", "vidhide", "luluvdo",
                    "streamtape", "mixdrop", "upstream", "rabbitstream",
                )
            )
        )
        if not like:
            continue
        if any(path.endswith(ext) for ext in (".js", ".css", ".png", ".jpg", ".svg", ".woff")):
            continue
        found.append(url)

    return _unique(found)


def _extract_direct_field(html: str) -> List[str]:
    found: List[str] = []
    for m in re.finditer(r'"direct"\s*:\s*"(https?://[^"]+)"', html, re.I):
        raw = m.group(1).replace("\\/", "/")
        if _is_valid_stream(raw):
            found.append(raw)
    return _unique(found)


def _extract_m3u8_loose(html: str) -> List[str]:
    found: List[str] = []
    for m in re.finditer(r"https?://[^\"'<>\\\s]+?\.m3u8[^\"'<>\\\s]*", html, re.I):
        raw = m.group(0).replace("\\/", "/")
        if _is_valid_stream(raw):
            found.append(raw)
    return _unique(found)


# ── HLS extract API ──────────────────────────────────────────


def _hlsextract(provider_url: str, token: str, embed_url: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "provider_url": provider_url,
        "status": None,
        "streams": [],
        "error": None,
    }
    try:
        r = _SESSION.post(
            HLS_EXTRACT_URL,
            headers={
                "Content-Type": "application/json",
                "Accept": "*/*",
                "Referer": embed_url,
                "Origin": BASE_URL.rstrip("/"),
                "User-Agent": USER_AGENT,
                "X-ULP-Token": token,  # nombre exacto que usa UnlimPlay
            },
            json={"url": provider_url},
            timeout=(_TIMEOUT_CONNECT, max(_TIMEOUT_READ, 35)),
            allow_redirects=True,
            proxies=_session_proxies(),
        )
        result["status"] = r.status_code
        if not r.text or not r.text.strip():
            result["error"] = f"empty_body_{r.status_code}"
            return result
        try:
            data = r.json()
        except ValueError:
            result["error"] = f"non_json_{r.status_code}"
            return result

        if not isinstance(data, dict):
            result["error"] = "invalid_response"
            return result

        if data.get("error") and not data.get("streams"):
            result["error"] = str(data.get("error"))
            return result

        streams = data.get("streams") or []
        if not isinstance(streams, list):
            streams = []

        valid: List[str] = []
        for s in streams:
            if not isinstance(s, str):
                continue
            cleaned = s.replace("\\/", "/")
            if not cleaned.startswith("http"):
                continue
            if _is_valid_stream(cleaned):
                valid.append(cleaned)

        result["streams"] = _unique(valid)
        return result
    except requests.RequestException as exc:
        result["error"] = f"request_error: {exc}"
        return result
    except Exception as exc:
        result["error"] = str(exc)
        return result


# ── select ───────────────────────────────────────────────────


def _select_best(streams: List[str]) -> Optional[str]:
    if not streams:
        return None
    return sorted(streams, key=_priority)[0]


# ── main ─────────────────────────────────────────────────────



def _cdn_headers(url: str, referer: str | None = None) -> dict:
    """
    Headers para CDNs de stream.
    vimeos.zip devuelve 403 si Referer es unlimplay.com;
    funciona con self-referer o sin Referer.
    """
    host = _host(url)
    h = {
        **_BROWSER_HEADERS,
        "Accept": "*/*",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "cross-site",
    }
    if "vimeos" in host:
        # Self-referer o nada — NO unlimplay
        h["Referer"] = url
        h.pop("Origin", None)
    else:
        ref = referer or (BASE_URL.rstrip("/") + "/")
        h["Referer"] = ref
        h["Origin"] = BASE_URL.rstrip("/")
    return h


def _AD_MARKERS():
    return (
        "tiktokcdn.com",
        "tiktok.com",
        "doubleclick.net",
        "googlesyndication",
        "/ad-site-",
    )


def _playlist_has_real_media(text: str, base_url: str) -> bool:
    """False si el m3u8 solo tiene ads (caso embedwish/vibuxer)."""
    ads = 0
    real = 0
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        low = s.lower()
        if any(m in low for m in _AD_MARKERS()):
            ads += 1
            continue
        real += 1
    if real > 0:
        return True
    # master sin media: tiene variantes .m3u8
    if ads == 0 and ("#EXT-X-STREAM-INF" in text or ".m3u8" in text.lower()):
        return True
    return False


def _probe_stream(url: str, referer: str) -> bool:
    """True si responde media/playlist con segmentos reales (no solo ads)."""
    if not url:
        return False
    try:
        r = _SESSION.get(
            url,
            headers=_cdn_headers(url, referer),
            timeout=(4, 8),
            allow_redirects=True,
            verify=False,
        )
        if r.status_code >= 400:
            return False
        body = r.content or b""
        head = body.lstrip()[:16]
        ctype = (r.headers.get("Content-Type") or "").lower()
        # MP4 directo
        if b"ftyp" in body[:64] or url.lower().split("?")[0].endswith(".mp4"):
            return True
        if not (head.startswith(b"#EXTM3U") or head.startswith(b"#EXT") or "mpegurl" in ctype):
            if "octet-stream" in ctype or "video/" in ctype:
                return True
            return False
        text = body.decode("utf-8", errors="replace")
        # Si es master, bajar la primera variante y validar media real
        if "#EXT-X-STREAM-INF" in text or (
            ".m3u8" in text and "seg-" not in text.lower() and "#EXTINF" not in text
        ):
            variant = None
            for line in text.splitlines():
                s = line.strip()
                if s and not s.startswith("#") and (".m3u8" in s.lower() or s.endswith(".txt") or "/index" in s.lower()):
                    variant = s if s.startswith("http") else urljoin(url.rsplit("/", 1)[0] + "/", s)
                    break
            if variant:
                try:
                    vr = _SESSION.get(
                        variant,
                        headers=_cdn_headers(variant, referer),
                        timeout=(4, 8),
                        verify=False,
                    )
                    if vr.status_code < 400:
                        vtext = (vr.text or "")
                        if not _playlist_has_real_media(vtext, variant):
                            print(f"[UNLIMPLAY] probe ads-only variant {variant[:80]}")
                            return False
                        return True
                except Exception:
                    return False
            # Sin variante validable → no confiar (embedwish master “vacío” de video)
            return False
        # Media playlist
        if not _playlist_has_real_media(text, url):
            print(f"[UNLIMPLAY] probe ads-only media {url[:80]}")
            return False
        return True
    except Exception as exc:
        print(f"[UNLIMPLAY] probe err: {exc}")
        return False


def _base_n(n: int, base: int) -> str:
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    if n == 0:
        return chars[0]
    s = ""
    while n:
        s = chars[n % base] + s
        n //= base
    return s



_PACKER_RE = re.compile(
    r"eval\(function\(p,a,c,k,e,(?:d|r)\).*?\}\('((?:\\'|[^'])*)',(\d+),(\d+),'((?:\\'|[^'])*)'\.split\('\|'\)",
    re.DOTALL,
)
_PACKER_RE2 = re.compile(
    r"eval\(function\(p,a,c,k,e,d\).*?\}\('((?:\\'|[^'])*)',(\d+),(\d+),'((?:\\'|[^'])*)'\.split\('\|'\)",
    re.DOTALL,
)

def _unpack_packer(payload: str, a: int, c: int, keys: list[str]) -> str:
    p = payload
    while c:
        c -= 1
        if c < len(keys) and keys[c]:
            p = re.sub(r"\b" + re.escape(_base_n(c, a)) + r"\b", keys[c], p)
    return p


def _extract_from_packed_html(html: str, page_url: str) -> List[str]:
    """Desempaqueta scripts tipo Dean Edwards y saca m3u8/mp4."""
    found: List[str] = []
    for rx in (_PACKER_RE, _PACKER_RE2):
        for m in rx.finditer(html):
            try:
                payload, a, c, kstr = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
                keys = kstr.split("|")
                decoded = _unpack_packer(payload, a, c, keys)
            except Exception:
                continue
            # links absolutos
            for u in re.findall(r"https?://[^\"'\\s<>]+", decoded):
                u = u.replace("\\/", "/")
                if _is_valid_stream(u):
                    found.append(u)
            # links.hls2 / hls3 / hls4 estilo embedwish
            for m2 in re.finditer(
                r'["\']?(?:hls[234]|file|src|source)["\']?\s*:\s*["\']([^"\']+)["\']',
                decoded,
                re.I,
            ):
                raw = m2.group(1).replace("\\/", "/")
                cleaned = _clean_url(raw, page_url)
                if cleaned and _is_valid_stream(cleaned):
                    found.append(cleaned)
            # relative /stream/.../master.m3u8
            for m2 in re.finditer(r'["\'](/stream/[^"\']+?\.m3u8[^"\']*)["\']', decoded, re.I):
                cleaned = _clean_url(m2.group(1), page_url)
                if cleaned:
                    found.append(cleaned)
                    # mirror hosts frecuentes del mismo path
                    path = m2.group(1)
                    for host in (
                        "https://embedwish.com",
                        "https://vibuxer.com",
                        "https://streamwish.to",
                        "https://streamhg.com",
                        "https://fastream.to",
                    ):
                        found.append(host + path)
    return _unique(found)


def _scrape_provider_page(provider_url: str, embed_url: str) -> List[str]:
    """
    Visita el embed del provider (embedwish, morencius, fastream…)
    y extrae streams del HTML / packer.
    """
    host = _host(provider_url)
    # Solo páginas de embed, no CDNs directos
    if any(
        x in host
        for x in (
            "vimeos.", "dramiyos", "acek-cdn", "premilkyway", "viatrix",
            "architectureguide", "homeautomationkit", "websitetrafficboost",
            "latestmusicchart", "agilebusiness",
        )
    ):
        return []
    if provider_url.lower().endswith((".m3u8", ".mp4", ".txt")):
        return []

    try:
        r = _SESSION.get(
            provider_url,
            headers={
                **_BROWSER_HEADERS,
                "Referer": embed_url or (BASE_URL.rstrip("/") + "/"),
                "Sec-Fetch-Dest": "iframe",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "cross-site",
            },
            timeout=(_TIMEOUT_CONNECT, 18),
            allow_redirects=True,
            verify=False,
        )
        if r.status_code >= 400 or not r.text:
            print(f"[UNLIMPLAY] provider page {host} status={r.status_code}")
            return []
        html = r.text
    except Exception as exc:
        print(f"[UNLIMPLAY] provider page fail {host}: {exc}")
        return []

    found = _extract_from_packed_html(html, r.url or provider_url)
    # también m3u8 sueltos en HTML
    for u in re.findall(r"https?://[^\"'\\s<>]+?\.m3u8[^\"'\\s<>]*", html, re.I):
        cleaned = _clean_url(u.replace("\\/", "/"))
        if cleaned:
            found.append(cleaned)
    for m in re.finditer(r'["\'](/stream/[^"\']+?\.m3u8[^"\']*)["\']', html, re.I):
        cleaned = _clean_url(m.group(1), r.url or provider_url)
        if cleaned:
            found.append(cleaned)

    found = _unique([f for f in found if _is_valid_stream(f)])
    if found:
        print(f"[UNLIMPLAY] provider scrape {host}: {len(found)} streams")
    return found


_MAX_PROVIDERS = 24      # antes: 12 (extract) / 6 (scrape)
_MAX_SCRAPE = 12
_EXTRACT_DEADLINE = 15.0  # s para extract + scrape (en paralelo)
_PROBE_DEADLINE = 14.0    # s por oleada de probes
_TOTAL_DEADLINE = 30.0    # s totales de la resolución
_WANT_WORKING = 3         # parar de sondear al tener N fuentes verificadas
_MAX_RETURN = 5           # fuentes que se entregan al player para failover
_PER_HOST = 2             # máx. fuentes por host (diversidad para el failover)


def _run_parallel(fn, items, workers: int, deadline_ts: float) -> list:
    """fn(item) en paralelo. Devuelve [(item, resultado)] de los que acabaron a tiempo."""
    out: list = []
    if not items:
        return out
    pool = ThreadPoolExecutor(max_workers=max(1, min(workers, len(items))))
    futs = {pool.submit(fn, it): it for it in items}
    try:
        for fut in as_completed(futs, timeout=max(0.1, deadline_ts - time.time())):
            try:
                out.append((futs[fut], fut.result()))
            except Exception as exc:  # noqa: BLE001
                print(f"[UNLIMPLAY] worker error: {exc}")
    except FutTimeout:
        print(f"[UNLIMPLAY] deadline: {len(out)}/{len(items)} terminaron")
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return out


def _diversify(urls: List[str], per_host: int = _PER_HOST) -> List[str]:
    seen: Dict[str, int] = {}
    out: List[str] = []
    for u in urls:
        h = _host(u)
        if seen.get(h, 0) >= per_host:
            continue
        seen[h] = seen.get(h, 0) + 1
        out.append(u)
    return out


def _empty_result(embed_url: str, error: str, detail: str = "") -> Dict[str, Any]:
    return {
        "stream_url": None,
        "stream_type": None,
        "candidates": [],
        "providers": [],
        "provider_results": [],
        "embed_url": embed_url,
        "ulp_token_available": False,
        "error": error,
        "error_detail": detail,
    }


def resolve_from_embed_url(embed_url: str) -> Dict[str, Any]:
    t0 = time.time()
    t_end = t0 + _TOTAL_DEADLINE
    print("[UNLIMPLAY] resolve", embed_url)

    try:
        html = _fetch_embed(embed_url)
    except EmbedError as exc:
        return _empty_result(embed_url, exc.code, str(exc))
    except Exception as exc:  # noqa: BLE001
        return _empty_result(embed_url, "embed_fetch_error", str(exc)[:160])

    token = _extract_ulp_token(html)
    if not token:
        print("[UNLIMPLAY] sin ULP token → renovando sesión")
        try:
            _reset_session()
            html = _fetch_embed(embed_url)
            token = _extract_ulp_token(html)
        except Exception as exc:  # noqa: BLE001
            print(f"[UNLIMPLAY] re-fetch tras reset falló: {exc}")

    providers = _extract_provider_urls(html, embed_url)[:_MAX_PROVIDERS]

    candidates: List[str] = []
    candidates.extend(_extract_direct_field(html))
    candidates.extend(_extract_m3u8_loose(html))

    # ── Etapa 1: extract + scrape de TODOS los providers, en paralelo ──
    cookies = _SESSION.cookies.copy()   # las comparten los hilos del pool
    state = {"token": token}

    def _task(job):
        kind, provider = job
        _SESSION.cookies.update(cookies)
        if kind == "ext":
            if not state["token"]:
                return {"provider_url": provider, "status": None, "streams": [], "error": "ulp_token_not_available"}
            return _hlsextract(provider, state["token"], embed_url)
        return _scrape_one(provider)

    def _scrape_one(provider: str) -> List[str]:
        try:
            return _scrape_provider_page(provider, embed_url)
        except Exception as exc:  # noqa: BLE001
            print(f"[UNLIMPLAY] scrape skip: {exc}")
            return []

    jobs = [("ext", p) for p in providers] + [("scr", p) for p in providers[:_MAX_SCRAPE]]
    done = _run_parallel(_task, jobs, workers=8, deadline_ts=min(t_end, time.time() + _EXTRACT_DEADLINE))

    provider_results: List[Dict[str, Any]] = []
    auth_failed: List[str] = []
    for (kind, provider), res in done:
        if kind == "ext":
            provider_results.append(res)
            err = str(res.get("error") or "")
            if res.get("status") in (401, 403) or "token" in err.lower():
                auth_failed.append(provider)
            candidates.extend(res.get("streams") or [])
        else:
            candidates.extend(res or [])

    # Token vencido: UNA renovación compartida y reintento solo de los que fallaron
    if auth_failed and len(auth_failed) >= max(1, len(provider_results) // 2) and time.time() < t_end:
        print(f"[UNLIMPLAY] {len(auth_failed)} providers con auth fail → refresh token (1 vez)")
        try:
            _reset_session()
            html2 = _fetch_embed(embed_url)
            token2 = _extract_ulp_token(html2)
            if token2:
                state["token"] = token2
                cookies = _SESSION.cookies.copy()
                retry = _run_parallel(
                    _task, [("ext", p) for p in auth_failed], workers=6,
                    deadline_ts=min(t_end, time.time() + 10),
                )
                for (_k, _p), res in retry:
                    provider_results.append(res)
                    candidates.extend(res.get("streams") or [])
        except Exception as exc:  # noqa: BLE001
            print(f"[UNLIMPLAY] refresh token fail: {exc}")

    candidates = [c for c in _unique(candidates) if _is_valid_stream(c)]
    candidates.sort(key=_priority)

    # ── Etapa 2: probe en oleadas hasta tener _WANT_WORKING fuentes OK ──
    working: List[str] = []
    probed = 0
    queue = list(candidates)
    while queue and len(working) < _WANT_WORKING and time.time() < t_end:
        wave, queue = queue[:6], queue[6:]
        results = _run_parallel(
            lambda c: _probe_stream(c, embed_url), wave, workers=6,
            deadline_ts=min(t_end, time.time() + _PROBE_DEADLINE),
        )
        probed += len(wave)
        for c, ok in results:
            if ok:
                working.append(c)
                print(f"[UNLIMPLAY] probe OK {c[:90]}")
            else:
                print(f"[UNLIMPLAY] probe FAIL {c[:90]}")

    working = _diversify(sorted(working, key=_priority))[:_MAX_RETURN]

    if working:
        stream_url = working[0]
        stream_type = "mp4" if ".mp4" in stream_url.lower() else "hls"
        out_candidates = working
        error = None
    else:
        stream_url = None
        stream_type = None
        # Sin verificadas: entrega las mejores SIN verificar para que el player pruebe
        out_candidates = _diversify(candidates)[:3]
        if not token:
            error = "no_stream_found_no_ulp_token"
        elif not providers:
            error = "no_stream_found_no_providers"
        elif candidates:
            error = "cdn_blocked_all_sources"
        else:
            error = "no_stream_found"

    result = {
        "stream_url": stream_url,
        "stream_type": stream_type,
        "candidates": out_candidates,
        "providers": providers[:30],
        "provider_results": [
            {
                "provider_url": p.get("provider_url"),
                "status": p.get("status"),
                "error": p.get("error"),
                "streams": (p.get("streams") or [])[:8],
            }
            for p in provider_results[:30]
        ],
        "embed_url": embed_url,
        "ulp_token_available": bool(state["token"]),
        "error": error,
        "stats": {
            "providers": len(providers),
            "candidates": len(candidates),
            "probed": probed,
            "working": len(working),
            "ms": int((time.time() - t0) * 1000),
        },
    }

    print(
        "[UNLIMPLAY] done",
        json.dumps(
            {
                "stream_url": (stream_url or "")[:100],
                "stream_type": stream_type,
                "error": error,
                **result["stats"],
            },
            ensure_ascii=False,
        ),
    )
    return result


def resolve_movie(content_id: str, imdb_id: Optional[str] = None) -> Dict[str, Any]:
    cid = imdb_id if imdb_id else content_id
    return resolve_from_embed_url(EMBED_MOVIE.format(content_id=cid))


def resolve_tv(
    content_id: str,
    season: int,
    episode: int,
    imdb_id: Optional[str] = None,
) -> Dict[str, Any]:
    cid = imdb_id if imdb_id else content_id
    return resolve_from_embed_url(
        EMBED_TV.format(content_id=cid, season=season, episode=episode)
    )


resolve_episode = resolve_tv