"""
Proxy HLS/MP4 local — todo el media por la misma caja (misma IP de salida).

Reglas:
  - NUNCA 302 al CDN (token/IP binding).
  - Reenviar Range → 200/206 tal cual.
  - Playlists: reescribir segmentos + #EXT-X-KEY + #EXT-X-MAP a /api/hls firmado.
  - UA Chrome + Referer por host.
  - Allowlist de hosts (SSRF).
"""
from __future__ import annotations

import ipaddress
import os
import re
import socket
import threading
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
import urllib3

from streams.signing import signed_query, verify_signed

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
_TIMEOUT = 30
_LOCK = threading.Lock()
_SESSIONS: Dict[str, requests.Session] = {}

# Referer por sufijo de host del CDN / embed
_REFERER_BY_SUFFIX: Tuple[Tuple[str, str], ...] = (
    ("vimeos.net", "https://vimeos.net/"),
    ("vimeos.zip", "https://vimeos.net/"),
    ("vimeus.com", "https://vimeus.com/"),
    ("videoapi.la", "https://videoapi.la/"),
    ("mxcontent.net", "https://mxdrop.click/"),
    ("mxdrop", "https://mxdrop.click/"),
    ("mixdrop", "https://mixdrop.ag/"),
    ("dood", "https://dood.watch/"),
    ("doodstream", "https://dood.watch/"),
    ("streamwish", "https://streamwish.to/"),
    ("vidhide", "https://vidhidepro.com/"),
    ("filemoon", "https://filemoon.sx/"),
    ("voe.sx", "https://voe.sx/"),
    ("brightpathsignals", "https://vidsrc.to/"),
    ("stellarconductor", "https://vidsrc.to/"),
    ("nextgencloudfabric", "https://vidsrc.to/"),
    ("profitablecreatorvault", "https://vidsrc.to/"),
    ("duskanddawn", "https://vidsrc.to/"),
    ("sololatino", "https://sololatino.net/"),
    ("playlatinsrc", "https://playlatinsrc.co/"),
)

# Allowlist de CDNs conocidos (además del chequeo anti-SSRF de IP privada).
# Vacío = solo chequeo DNS/IP. Con STREAM_HOST_ALLOW=*.cdn.com,otro.com
_DEFAULT_ALLOW_SUFFIXES = (
    "vimeos.net",
    "vimeos.zip",
    "vimeus.com",
    "mxcontent.net",
    "mxdrop.click",
    "mixdrop",
    "dood.watch",
    "doodstream",
    "streamwish",
    "vidhide",
    "filemoon",
    "voe.sx",
    "brightpathsignals.com",
    "stellarconductornexus.com",
    "nextgencloudfabric.com",
    "profitablecreatorvault.site",
    "duskanddawn.space",
    "videoapi.la",
    "embed69.org",
    "sololatino.net",
    "playlatinsrc.co",
    "tapecontent.net",
    "streamtape.com",
    "cuevana3",
    "cuevana",
    "vidsrc.to",
    "vidsrc.me",
    "vidsrc.in",
    "2embed.skin",
    "fembed.com",
    "feurl.com",
    "cdn",
    "cloudfront.net",
    "akamai",
    "fastly",
)


def _proxy_mode() -> str:
    # full = segmentos + keys por nuestra caja (recomendado Oracle/VPS)
    # manifest_only = solo m3u8 (ahorra egress, rompe si token atado a IP)
    return (os.environ.get("STREAM_PROXY_MODE") or "full").strip().lower()


def _session_for(host: str) -> requests.Session:
    host = (host or "").lower()
    with _LOCK:
        s = _SESSIONS.get(host)
        if s is None:
            s = requests.Session()
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=25,
                pool_maxsize=50,
                max_retries=1,
            )
            s.mount("https://", adapter)
            s.mount("http://", adapter)
            s.headers.update(
                {
                    "User-Agent": _UA,
                    "Accept": "*/*",
                    "Accept-Language": "es-419,es;q=0.9,en;q=0.8",
                    "Connection": "keep-alive",
                }
            )
            _SESSIONS[host] = s
        return s


def _referer_for(host: str, explicit: str = "") -> str:
    if explicit:
        return explicit
    h = (host or "").lower()
    for suf, ref in _REFERER_BY_SUFFIX:
        if h == suf or h.endswith("." + suf) or suf in h:
            return ref
    if h:
        return f"https://{h}/"
    return "https://www.google.com/"


def _allow_suffixes() -> tuple:
    extra = (os.environ.get("STREAM_HOST_ALLOW") or "").strip()
    parts = [p.strip().lower().lstrip(".") for p in extra.split(",") if p.strip()]
    return tuple(_DEFAULT_ALLOW_SUFFIXES) + tuple(parts)


def _host_allowed(host: str) -> bool:
    """Allowlist de hosts (HOST_SUFFIXES con endswith) para evitar SSRF y proxy abierto."""
    strict = (os.environ.get("STREAM_HOST_STRICT") or "1").lower() not in ("0", "false", "no")
    if not strict:
        return True
    h = (host or "").lower()
    for suf in _allow_suffixes():
        if h == suf or h.endswith("." + suf) or suf in h:
            return True
    return False


def _host_ok(url: str) -> Tuple[bool, str]:
    if not url.startswith("https://"):
        return False, "solo_https"
    try:
        p = urlparse(url)
        host = (p.hostname or "").lower()
        if not host:
            return False, "sin_host"
        if p.port not in (None, 443):
            return False, "puerto_no_443"
        if not _host_allowed(host):
            return False, "host_not_allowed"
        for info in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM):
            ip = ipaddress.ip_address(info[4][0])
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
                or ip.is_unspecified
            ):
                return False, "ip_privada"
        return True, "ok"
    except Exception as exc:
        return False, f"dns:{exc}"


def _normalize_vod(text: str) -> str:
    if "#EXT-X-STREAM-INF" in text:
        return text
    if "#EXT-X-ENDLIST" in text:
        return text
    if "#EXT-X-PLAYLIST-TYPE:EVENT" in text or "#EXT-X-PLAYLIST-TYPE:LIVE" in text:
        return text
    if "#EXTINF" not in text:
        return text
    body = text.rstrip() + "\n"
    if "#EXT-X-PLAYLIST-TYPE" not in body:
        body += "#EXT-X-PLAYLIST-TYPE:VOD\n"
    body += "#EXT-X-ENDLIST\n"
    return body


def _is_playlist_url(u: str) -> bool:
    low = (u or "").lower().split("?")[0]
    return (
        low.endswith(".m3u8")
        or low.endswith(".m3u")
        or "/urlset" in low
        or ("master" in low and "m3u" in low)
    )


def _cf_image_trick(url: str) -> str:
    """Opcional: .ts → .jpg en la URL proxy (CF a veces trata como imagen)."""
    if (os.environ.get("STREAM_CF_TS_JPG") or "0").lower() not in ("1", "true", "yes"):
        return url
    if ".ts" in url:
        return re.sub(r"\.ts(\?|$)", r".jpg\1", url, count=1)
    return url


def _rewrite_playlist(
    text: str,
    base_url: str,
    ref: str,
    origin: str = "",
    *,
    mode: str = "full",
) -> str:
    """
    mode=full: segmentos + KEY + MAP por /api/hls (misma IP).
    mode=manifest_only: solo playlists anidadas por proxy.
    """
    prefix = (origin or "").rstrip("/") + "/api/hls"
    mode = (mode or "full").lower()

    def prox(u: str) -> str:
        return f"{prefix}?{signed_query(_cf_image_trick(u), ref=ref)}"

    def map_uri(abs_u: str) -> str:
        if mode == "full":
            return prox(abs_u)
        if _is_playlist_url(abs_u):
            return prox(abs_u)
        return abs_u

    out = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            if 'URI="' in stripped:
                m = re.search(r'URI="([^"]+)"', stripped)
                if m:
                    try:
                        abs_u = urljoin(base_url, m.group(1))
                        mapped = map_uri(abs_u)
                        out.append(
                            re.sub(
                                r'URI="[^"]+"',
                                f'URI="{mapped}"',
                                stripped,
                                count=1,
                            )
                        )
                        continue
                    except Exception:
                        pass
            out.append(line)
            continue
        try:
            abs_u = urljoin(base_url, stripped)
            out.append(map_uri(abs_u))
        except Exception:
            out.append(line)
    rewritten = "\n".join(out) + ("\n" if text.endswith("\n") else "")
    return _normalize_vod(rewritten)


def handle_hls(handler: Any, query: Dict[str, str]) -> None:
    parsed, why = verify_signed(query)
    if parsed is None:
        return _json_err(handler, 403, why)

    url, ref = parsed
    ok, reason = _host_ok(url)
    if not ok:
        return _json_err(handler, 403, reason)

    host = (urlparse(url).hostname or "").lower()
    sess = _session_for(host)
    ref_final = _referer_for(host, ref)

    headers = {
        "User-Agent": _UA,
        "Accept": "*/*",
        "Accept-Language": "es-419,es;q=0.9,en;q=0.8",
        "Referer": ref_final,
    }
    try:
        headers["Origin"] = f"{urlparse(ref_final).scheme}://{urlparse(ref_final).netloc}"
    except Exception:
        pass

    # Range crítico para seek (206)
    range_hdr = (handler.headers.get("Range") or "").strip()
    if range_hdr and re.fullmatch(r"bytes=\d*-\d*", range_hdr):
        headers["Range"] = range_hdr

    try:
        upstream = None
        # Para segmentos (.ts, .m4s, .mp4, etc.): usar SIEMPRE requests.Session
        # con HTTP Keep-Alive reutilizando el socket TLS. curl_cffi sin sesión
        # destruye la conexión y renegocia TLS en cada segmento (lag de 1-2s por fragmento).
        if not _is_playlist_url(url):
            try:
                upstream = sess.get(
                    url,
                    headers=headers,
                    timeout=_TIMEOUT,
                    stream=True,
                    verify=False,
                    allow_redirects=True,
                )
            except Exception:
                upstream = None

        if upstream is None:
            try:
                from curl_cffi import requests as creq

                upstream = creq.get(
                    url,
                    headers=headers,
                    timeout=_TIMEOUT,
                    stream=True,
                    verify=False,
                    allow_redirects=True,
                    impersonate="chrome131",
                )
            except Exception:
                upstream = sess.get(
                    url,
                    headers=headers,
                    timeout=_TIMEOUT,
                    stream=True,
                    verify=False,
                    allow_redirects=True,
                )
    except Exception as exc:
        print(f"[hls-proxy] upstream fail {url[:80]}: {exc}", flush=True)
        return _json_err(handler, 502, f"upstream:{exc}")

    final = getattr(upstream, "url", None) or url
    ok, reason = _host_ok(final)
    if not ok:
        try:
            upstream.close()
        except Exception:
            pass
        return _json_err(handler, 403, f"redirect_{reason}")

    status = upstream.status_code
    # Nunca redirigimos al cliente: si el upstream es 3xx ya lo siguió requests.
    if status in (301, 302, 303, 307, 308):
        try:
            upstream.close()
        except Exception:
            pass
        return _json_err(handler, 502, f"unexpected_redirect:{status}")

    ctype = (upstream.headers.get("Content-Type") or "").lower()

    peek = b""
    try:
        for chunk in upstream.iter_content(chunk_size=16 * 1024):
            if chunk:
                peek = chunk
                break
    except Exception as exc:
        try:
            upstream.close()
        except Exception:
            pass
        return _json_err(handler, 502, f"read:{exc}")

    is_pl = (
        "mpegurl" in ctype
        or "m3u8" in ctype
        or ".m3u8" in final.lower()
        or peek.lstrip().startswith(b"#EXTM3U")
    )

    if is_pl or (".m3u8" in final.lower() and not peek.startswith(b"\x00")):
        rest = b"".join(upstream.iter_content(chunk_size=64 * 1024))
        try:
            upstream.close()
        except Exception:
            pass
        body = peek + rest
        try:
            text = body.decode("utf-8", errors="replace")
        except Exception:
            text = body.decode("latin-1", errors="replace")

        if text.lstrip().startswith("#EXTM3U"):
            req_host = (handler.headers.get("Host") or "localhost:8000").strip()
            xf = (handler.headers.get("X-Forwarded-Proto") or "").split(",")[0].strip()
            scheme = xf if xf in ("http", "https") else "http"
            origin = f"{scheme}://{req_host}"
            mode = _proxy_mode()
            rewritten = _rewrite_playlist(
                text,
                final,
                ref_final,
                origin=origin,
                mode=mode,
            )
            data = rewritten.encode("utf-8")
            handler.send_response(200)
            handler.send_header("Content-Type", "application/vnd.apple.mpegurl")
            handler.send_header("Content-Length", str(len(data)))
            handler.send_header("Access-Control-Allow-Origin", "*")
            handler.send_header("Cache-Control", "public, max-age=10")
            handler.end_headers()
            try:
                handler.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return

        print(
            f"[hls-proxy] not_playlist status={status} ctype={ctype} head={text[:120]!r}",
            flush=True,
        )
        return _json_err(handler, 502, "not_a_playlist")

    # Segmento / MP4 — passthrough con el mismo status (200 o 206)
    if status not in (200, 206):
        try:
            upstream.close()
        except Exception:
            pass
        return _json_err(handler, 502, f"upstream_status:{status}")

    handler.send_response(status)
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header(
        "Access-Control-Expose-Headers",
        "Content-Length, Content-Range, Accept-Ranges",
    )
    out_ctype = upstream.headers.get("Content-Type") or "application/octet-stream"
    if "html" in (out_ctype or "").lower() and status in (200, 206):
        out_ctype = "video/mp4"
    if final.lower().split("?")[0].endswith(".mp4"):
        out_ctype = upstream.headers.get("Content-Type") or "video/mp4"
    if final.lower().split("?")[0].endswith(".ts"):
        out_ctype = "video/mp2t"
    handler.send_header("Content-Type", out_ctype)
    for h in ("Content-Length", "Content-Range", "Accept-Ranges"):
        v = upstream.headers.get(h)
        if v:
            handler.send_header(h, v)
    # Cache generoso para segmentos inmutables (evita re-descargas y micro-pausas)
    handler.send_header("Cache-Control", "public, max-age=86400")
    handler.end_headers()
    try:
        if peek:
            handler.wfile.write(peek)
        for chunk in upstream.iter_content(chunk_size=128 * 1024):
            if chunk:
                handler.wfile.write(chunk)
    except (BrokenPipeError, ConnectionResetError):
        pass
    finally:
        try:
            upstream.close()
        except Exception:
            pass


def _json_err(handler: Any, status: int, error: str) -> None:
    import json

    body = json.dumps({"error": error}).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    try:
        handler.wfile.write(body)
    except (BrokenPipeError, ConnectionResetError):
        pass