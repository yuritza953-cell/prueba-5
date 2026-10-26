"""
Proxy HLS firmado + con streaming.

- Solo sirve URLs FIRMADAS (HMAC) por el propio servidor: ya no es un proxy
  abierto y no necesitas mantener listas de hosts a mano.
- Valida SSRF: https, puerto 443, DNS público, y cada redirect.
- Playlists reescritas con URLs RELATIVAS (funcionan igual bajo /.proxy
  de Discord, en Fly o en /bot/...).
- Segmentos: caché en RAM + single-flight (5 viewers = 1 descarga),
  streaming + Range para MP4 / archivos grandes.
- Recuerda por host qué combinación (referer, verify) funcionó.
- Mixdrop CDN (mxcontent.net): nunca usa Referer=URL del mp4; prioriza
  sin Referer / mxdrop.* y salida directa antes que proxies.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import http.cookiejar
import ipaddress
import os
import re
import secrets
import socket
import threading
import time
from typing import Callable, Dict, Iterator, List, Optional, Tuple
from urllib.parse import parse_qs, urljoin, urlparse, quote

import requests
from requests.adapters import HTTPAdapter
from flask import Blueprint, Response, jsonify, request

from .flight import SingleFlight, TTLCache

hls_bp = Blueprint("hls_proxy", __name__)

DEBUG = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")

# ── Firma ─────────────────────────────────────────────────────────

_env_key = os.environ.get("PROXY_SIGNING_KEY", "")
_SIGN_KEY = _env_key.encode() if _env_key else secrets.token_bytes(32)
if not _env_key:
    print(
        "[hls-proxy] PROXY_SIGNING_KEY no definida: uso clave aleatoria "
        "(los links firmados caducan al reiniciar). Define el secret en Fly."
    )

_SIGN_TTL = 6 * 3600  # una peli larga + margen
_DEFAULT_REF = "https://unlimplay.com/"


def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode((s + "=" * (-len(s) % 4)).encode("ascii"))


def _mac(url: str, ref: str, exp: int) -> str:
    msg = f"{exp}\n{ref}\n{url}".encode("utf-8")
    return _b64e(hmac.new(_SIGN_KEY, msg, hashlib.sha256).digest()[:16])


def signed_query(url: str, ref: str = "", ttl: int = _SIGN_TTL) -> str:
    exp = int(time.time()) + ttl
    q = f"u={_b64e(url.encode('utf-8'))}&e={exp}&s={_mac(url, ref, exp)}"
    if ref:
        q += f"&r={_b64e(ref.encode('utf-8'))}"
    return q


def proxy_path(url: str, ref: str = "") -> str:
    """Ruta firmada para el cliente: '/api/hls?u=...'. El front le antepone su base."""
    return "/api/hls?" + signed_query(url, ref)


def _verify(args) -> Tuple[Optional[Tuple[str, str]], str]:
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


# ── SSRF ──────────────────────────────────────────────────────────

_DNS_OK = TTLCache(ttl=300, max_items=512)


def _ip_blocked(ip_str: str) -> bool:
    ip = ipaddress.ip_address(ip_str.split("%")[0])
    return (
        ip.is_private or ip.is_loopback or ip.is_link_local
        or ip.is_reserved or ip.is_multicast or ip.is_unspecified
    )


def host_matches_suffix(host: str, suffixes: tuple) -> bool:
    host = (host or "").lower().rstrip(".")
    return any(host == s.lower() or host.endswith("." + s.lower()) for s in suffixes)


def validate_public_https(url: str) -> Tuple[bool, str]:
    """https + puerto 443 + el host resuelve SOLO a IPs públicas."""
    if not url or not url.startswith("https://"):
        return False, "solo https"
    try:
        p = urlparse(url)
        host = (p.hostname or "").lower()
        port = p.port
    except ValueError:
        return False, "url malformada"
    if not host or host in ("localhost",):
        return False, "host bloqueado"
    if port not in (None, 443):
        return False, "puerto no permitido"
    try:
        return (False, "IP privada") if _ip_blocked(host) else (True, "ok")
    except ValueError:
        pass  # no es IP literal → resolver DNS
    cached = _DNS_OK.get(host)
    if cached is None:
        try:
            infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
            cached = bool(infos) and not any(_ip_blocked(i[4][0]) for i in infos)
        except socket.gaierror:
            cached = False
        _DNS_OK.set(host, cached, ttl=300 if cached else 20)
    return (True, "ok") if cached else (False, "dns no público / no resuelve")


# ── Egress opcional (PROXY_LIST de keep_alive) ────────────────────

_egress: Callable[[], List[Optional[dict]]] = lambda: [None]


def configure(egress: Optional[Callable[[], List[Optional[dict]]]] = None) -> None:
    global _egress
    if egress:
        _egress = egress


# ── HTTP upstream ─────────────────────────────────────────────────

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
_SESS = requests.Session()
_SESS.mount("https://", HTTPAdapter(pool_connections=20, pool_maxsize=64))
# Sin cookies: nada se arrastra entre CDNs ni entre usuarios.
_SESS.cookies.set_policy(http.cookiejar.DefaultCookiePolicy(allowed_domains=[]))

_TIMEOUT = (6, 45)          # connect, read — MP4 grandes necesitan más margen
_SEG_MAX = 8 * 1024 * 1024  # segmentos hasta 8 MB se bufferizan/cachean
_PL_MAX = 4 * 1024 * 1024
_COMBO = TTLCache(ttl=3600, max_items=512)   # host -> (kind, verify) que funcionó
_BODY_CACHE = TTLCache(ttl=120, max_bytes=48 * 1024 * 1024, max_items=96)
_FLIGHT = SingleFlight()
# Proxy que funcionó por host (mismo IP para todos los Range de una peli)
_STICKY_PROXY = TTLCache(ttl=300, max_items=128)

_MIX_CDN_REFS = (
    "https://mxdrop.click/",
    "https://mxdrop.to/",
    "https://mixdrop.ag/",
    "https://mixdrop.to/",
)


def _is_mix_cdn(host: str) -> bool:
    h = (host or "").lower()
    return (
        "mxcontent.net" in h
        or "mixdrop" in h
        or h.endswith("mxdrop.click")
        or h.endswith("mxdrop.to")
    )


class _Blocked(Exception):
    pass


class _UpstreamFail(Exception):
    def __init__(self, status: int, reason: str):
        super().__init__(reason)
        self.status = status
        self.reason = reason


def _upstream_get(url, headers, verify, proxies):
    """GET con redirects manuales (<=4), validando cada salto."""
    for _ in range(5):
        ok, why = validate_public_https(url)
        if not ok:
            raise _Blocked(why)
        r = _SESS.get(
            url, headers=headers, timeout=_TIMEOUT, allow_redirects=False,
            stream=True, verify=verify, proxies=proxies,
        )
        loc = r.headers.get("Location")
        if r.status_code in (301, 302, 303, 307, 308) and loc:
            r.close()
            url = urljoin(url, loc)
            continue
        return r, url
    raise _Blocked("demasiados redirects")


def _collect_egress(is_mix: bool) -> List[Optional[dict]]:
    """Reúne hasta ~todos los proxies del pool (keep_alive solo entrega 3 por llamada)."""
    seen = []
    keys = set()
    for _ in range(6):
        for p in _egress():
            key = "direct" if p is None else str(sorted(p.items()))
            if key in keys:
                continue
            keys.add(key)
            seen.append(p)
    if not is_mix:
        return seen or [None]
    proxied = [p for p in seen if p is not None]
    directs = [p for p in seen if p is None]
    # sticky / proxies primero; directo al final
    return (proxied + directs) or [None]


def _fetch_upstream(url: str, ref: str, rng: str):
    host = (urlparse(url).hostname or "").lower()
    ref = ref or _DEFAULT_REF
    is_mix = _is_mix_cdn(host)

    refs: Dict[str, str] = {"ref": ref, "none": ""}
    if not is_mix:
        refs["self"] = url
    if is_mix:
        for i, extra in enumerate(_MIX_CDN_REFS):
            if extra.rstrip("/") != (ref or "").rstrip("/"):
                refs[f"mx{i}"] = extra
        order = ["none", "ref"] + [k for k in refs if k.startswith("mx")]
    else:
        order = ["self", "ref", "none"]

    learned = _COMBO.get(host)
    if learned and learned[0] in order:
        order = [learned[0]] + [k for k in order if k != learned[0]]

    last_status: Optional[int] = None
    last_err: Optional[Exception] = None
    attempts_log: List[str] = []

    egress_list = _collect_egress(is_mix)
    sticky = _STICKY_PROXY.get(host)
    if sticky is not None:
        # Mismo proxy que ya sirvió un Range de este host
        rest = [p for p in egress_list if p != sticky]
        egress_list = [sticky] + rest

    for proxies in egress_list:
        timed_out = False
        got_403 = False
        via = "proxy" if proxies else "direct"
        for kind in order:
            verify = learned[1] if (learned and learned[0] == kind) else True
            ref_try = refs.get(kind, "")
            headers = {
                "User-Agent": _UA,
                "Accept": "*/*",
                "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
                "Accept-Encoding": "identity",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "cross-site",
            }
            if ref_try:
                headers["Referer"] = ref_try
                if not is_mix:
                    p = urlparse(ref_try)
                    if p.scheme and p.netloc:
                        headers["Origin"] = f"{p.scheme}://{p.netloc}"
            if rng:
                headers["Range"] = rng

            for _attempt in (0, 1):
                try:
                    r, final = _upstream_get(url, headers, verify, proxies)
                except requests.exceptions.SSLError as exc:
                    last_err = exc
                    if verify:
                        verify = False
                        continue
                    break
                except (requests.Timeout, requests.ConnectionError) as exc:
                    last_err = exc
                    timed_out = True
                    attempts_log.append(f"{via}/{kind}:timeout")
                    break
                if r.status_code < 400:
                    _COMBO.set(host, (kind, verify))
                    if proxies is not None:
                        _STICKY_PROXY.set(host, proxies)
                    print(
                        f"[hls-proxy] OK {r.status_code} host={host} kind={kind} via={via}"
                        + (f" range={rng[:28]}" if rng else "")
                    )
                    return r, final
                last_status = r.status_code
                attempts_log.append(f"{via}/{kind}:{r.status_code}")
                r.close()
                if r.status_code == 403:
                    got_403 = True
                    # En mix CDN un 403 con este proxy → probar otro proxy ya
                    if is_mix:
                        break
                break
            if is_mix and got_403:
                break
            if timed_out:
                break
        if timed_out and not is_mix:
            break

    detail = ",".join(attempts_log[-12:]) if attempts_log else (str(last_err) if last_err else "sin respuesta")
    print(f"[hls-proxy] FAIL {last_status or 502} host={host} tries={detail}")
    raise _UpstreamFail(last_status or 502, detail[:180])


# ── Reescritura de playlists ──────────────────────────────────────

_AD_MARKERS = (
    "tiktokcdn.com", "tiktok.com", "doubleclick.net", "googlesyndication",
    "googletagservices", "adservice.google", "/ad-site-", "adsystem", "facebook.com/tr",
)


def _is_ad_url(u: str) -> bool:
    low = (u or "").lower()
    return any(m in low for m in _AD_MARKERS)


def _rewrite_playlist(text: str, base_url: str, ref: str) -> Tuple[str, int, int]:
    tok = (parse_qs(urlparse(base_url).query).get("token") or [None])[0]

    def prox(u: str) -> str:
        if tok and "token=" not in u:
            u += ("&" if "?" in u else "?") + "token=" + quote(str(tok), safe="")
        return "hls?" + signed_query(u, ref)   # RELATIVA: hereda /.proxy, /bot, etc.

    out: List[str] = []
    n_media = n_ads = 0

    def repl(m: "re.Match") -> str:
        nonlocal n_ads
        raw = m.group(1)
        if not raw or raw.startswith("data:"):
            return m.group(0)
        u = urljoin(base_url, raw)
        if _is_ad_url(u):
            n_ads += 1
            return 'URI=""'
        return f'URI="{prox(u)}"'

    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            if "URI=" in s:
                s = re.sub(r'URI="([^"]*)"', repl, s)
            out.append(s)
            continue
        u = urljoin(base_url, s)
        if _is_ad_url(u):
            n_ads += 1
            if out and out[-1].startswith("#EXTINF"):
                out.pop()
            continue
        out.append(prox(u))
        n_media += 1
    return "\n".join(out) + "\n", n_media, n_ads


# ── Construcción de la respuesta ──────────────────────────────────


class _Built:
    def __init__(self, status, body, ctype, headers=None, stream=None, ttl=0):
        self.status = status
        self.body = body
        self.ctype = ctype
        self.headers = headers or {}
        self.stream: Optional[Iterator[bytes]] = stream
        self.ttl = ttl
        self._claimed = False
        self._lk = threading.Lock()

    def take(self) -> bool:
        """Un stream solo lo puede consumir UNA petición; los buffers, todas."""
        if self.stream is None:
            return True
        with self._lk:
            if self._claimed:
                return False
            self._claimed = True
            return True


def _gen(chunks: List[bytes], it, r) -> Iterator[bytes]:
    try:
        for c in chunks:
            yield c
        for c in it:
            if c:
                yield c
    finally:
        r.close()


def _pass_headers(r) -> Dict[str, str]:
    h = {"Accept-Ranges": r.headers.get("Accept-Ranges", "bytes")}
    if r.headers.get("Content-Range"):
        h["Content-Range"] = r.headers["Content-Range"]
    if r.headers.get("Content-Length") and not r.headers.get("Content-Encoding"):
        h["Content-Length"] = r.headers["Content-Length"]
    return h


def _build(url: str, ref: str, rng: str) -> _Built:
    r, final = _fetch_upstream(url, ref, rng)
    try:
        it = r.iter_content(64 * 1024)
        first = next(it, b"")
        ctype = (r.headers.get("Content-Type") or "application/octet-stream")
        head = first.lstrip(b"\xef\xbb\xbf \r\n\t")[:8]

        if head.startswith(b"#EXT") or ("mpegurl" in ctype.lower() and head[:1] == b"#"):
            parts, size = [first], len(first)
            for c in it:
                parts.append(c)
                size += len(c)
                if size > _PL_MAX:
                    raise _UpstreamFail(502, "playlist_too_large")
            r.close()
            text = b"".join(parts).decode("utf-8", errors="replace")
            body, n_media, n_ads = _rewrite_playlist(text, final, ref)
            if n_media == 0 and n_ads > 0:
                raise _UpstreamFail(502, "playlist_ads_only")
            print(f"[hls-proxy] playlist OK media={n_media} ads_stripped={n_ads}")
            return _Built(
                200, body.encode("utf-8"), "application/vnd.apple.mpegurl",
                {"Cache-Control": "no-cache"}, ttl=5,
            )

        if head.startswith(b"{") and b'"error"' in first[:300].lower():
            r.close()
            raise _UpstreamFail(502, "upstream_json_error")

        hdrs = _pass_headers(r)
        try:
            clen = int(r.headers.get("Content-Length", "-1"))
        except ValueError:
            clen = -1
        if rng or r.status_code == 206 or clen > _SEG_MAX:
            return _Built(r.status_code, None, ctype, hdrs, stream=_gen([first], it, r))

        parts, size = [first], len(first)
        for c in it:
            parts.append(c)
            size += len(c)
            if size > _SEG_MAX:      # resultó ser grande: seguir en streaming
                hdrs.pop("Content-Length", None)
                return _Built(r.status_code, None, ctype, hdrs, stream=_gen(parts, it, r))
        r.close()
        hdrs.pop("Content-Length", None)  # Flask lo calcula
        hdrs["Cache-Control"] = "private, max-age=300"
        return _Built(r.status_code, b"".join(parts), ctype, hdrs, ttl=120)
    except BaseException:
        r.close()
        raise


def _serve(url: str, ref: str, rng: str) -> _Built:
    key = (url, ref)
    if not rng:
        hit = _BODY_CACHE.get(key)
        if hit is not None:
            return hit

    def work() -> _Built:
        b = _build(url, ref, rng)
        if not rng and b.body is not None and b.status == 200:
            _BODY_CACHE.set(key, b, size=len(b.body), ttl=b.ttl)
        return b

    b = _FLIGHT.do((url, ref, rng), work)
    if not b.take():          # el líder ya consumió el stream: pide el tuyo
        b = _build(url, ref, rng)
    return b


def _respond(b: _Built) -> Response:
    h = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Expose-Headers": "Content-Length, Content-Range, Accept-Ranges",
        **b.headers,
    }
    body = b.stream if b.stream is not None else b.body
    return Response(body, status=b.status, content_type=b.ctype, headers=h,
                    direct_passthrough=b.stream is not None)


def _err(status: int, error: str, **extra):
    resp = jsonify({"error": error, **extra})
    resp.status_code = status
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


@hls_bp.route("/api/hls")
@hls_bp.route("/bot/api/hls")
def api_hls():
    parsed, why = _verify(request.args)
    if parsed is None:
        return _err(403, "url_bloqueada", reason=why)
    url, ref = parsed
    ok, why = validate_public_https(url)
    if not ok:
        return _err(403, "url_bloqueada", reason=why)

    rng = (request.headers.get("Range") or "").strip()
    if rng and not re.fullmatch(r"bytes=\d*-\d*", rng):
        rng = ""
    try:
        return _respond(_serve(url, ref, rng))
    except _Blocked as exc:
        return _err(403, "redirect_bloqueado", reason=str(exc))
    except _UpstreamFail as exc:
        print(f"[hls-proxy] FAIL {exc.status} {exc.reason[:120]} host={urlparse(url).hostname}")
        return _err(502, exc.reason if exc.reason.startswith(("playlist_", "upstream_json")) else "upstream_error",
                    upstream_status=exc.status, detail=exc.reason[:200] if DEBUG else None)