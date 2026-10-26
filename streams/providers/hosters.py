"""
Resolvers de hosters (ES/EN) — sin depender de un agregador.

Incluye:
  • StreamWish / Hlswish / Flaswish — carrera de mirrors + packer
  • VidHide / Morencius / Filelions — packer → /stream/.../master.m3u8
  • VOE — ofuscación LUT (César + tabla + doble base64)
  • Detección HLS sin extensión (.jpg segments, format=m3u8-aapl, etc.)
  • Filemoon — attestation ECDSA (esqueleto; necesita challenge vivo)

Uso desde embed69 / playlatin / unlimplay:
    from modules.providers.hosters import resolve_hoster_url
    streams = resolve_hoster_url("https://flaswish.com/e/xxxx")
"""
from __future__ import annotations

import base64
import json
import re
import struct
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Sequence, Tuple
from urllib.parse import urljoin, urlparse

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
_TIMEOUT = 7

# ── Dominios espejo (familia MIRRORS) ─────────────────────────────

STREAMWISH_MIRRORS = (
    "flaswish.com",
    "swishsrv.com",
    "streamwish.top",
    "streamwish.to",
    "strwish.com",
    "hglink.to",
    "hlswish.com",
    "swhoi.com",
    "streamwish.site",
)

VIDHIDE_MIRRORS = (
    "morencius.com",
    "vidhide.com",
    "vidhidepro.com",
    "filelions.top",
    "filelions.com",
    "callistanise.com",
    "vidhideplus.com",
)

VOE_MIRRORS = (
    "voe.sx",
    "voe-unblock.com",
    "voeunblock.com",
    "voeun-block.net",
    "voe4k.com",
)

FILEMOON_MIRRORS = (
    "filemoon.sx",
    "filemoon.to",
    "filemoon.eu",
    "bysekoze.com",
    "kerapoxy.cc",
)

FEMBED_MIRRORS = (
    "fembed.com",
    "feurl.com",
    "femax20.com",
    "fcdn.stream",
    "dutrag.com",
    "layarkaca21.org",
)

# ── Packer (Dean Edwards, sin eval) ───────────────────────────────

_PACKER_RE = re.compile(
    r"eval\(function\(p,a,c,k,e,(?:d|r)\).*?\}\('((?:\\'|[^'])*)',(\d+),(\d+),'((?:\\'|[^'])*)'\.split\('\|'\)",
    re.DOTALL,
)


def _base_n(n: int, base: int) -> str:
    chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if n == 0:
        return "0"
    s = ""
    while n:
        s = chars[n % base] + s
        n //= base
    return s


def unpack_packer(html: str) -> str:
    parts: List[str] = []
    for m in _PACKER_RE.finditer(html or ""):
        try:
            payload, a, c, kstr = (
                m.group(1),
                int(m.group(2)),
                int(m.group(3)),
                m.group(4),
            )
            keys = kstr.split("|")
            p = payload
            while c:
                c -= 1
                if c < len(keys) and keys[c]:
                    p = re.sub(
                        r"\b" + re.escape(_base_n(c, a)) + r"\b", keys[c], p
                    )
            parts.append(p)
        except Exception:
            continue
    return "\n".join(parts)


# ── Detección de streams (sin exigir extensión) ───────────────────

_STREAM_HINTS = (
    ".m3u8",
    ".mp4",
    "format=m3u8",
    "type=hls",
    "mpegurl",
    "/hls2/",
    "/hls3/",
    "/hls4/",
    "/stream/",
    "master.txt",
    "index-v1",
)


def looks_like_stream(url: str) -> bool:
    u = (url or "").lower()
    if not u.startswith("http"):
        return False
    # Demasiado corto o path vacío → basura del packer
    if len(u) < 40:
        return False
    path = u.split("?", 1)[0]
    # Truco .jpg: segmentos TS disfrazados
    if path.endswith((".jpg", ".jpeg", ".png", ".html")):
        return any(h in u for h in ("/hls", "seg-", "segment", "index-", "frag"))
    if ".m3u8" in u or ".mp4" in u or "master.txt" in u:
        return True
    if any(h in u for h in ("/hls2/", "/hls3/", "/hls4/", "format=m3u8", "type=hls")):
        return True
    # /stream/xxx/yyy/master.m3u8 (no solo /stream/)
    if "/stream/" in path and path.count("/") >= 4:
        return True
    return False


def extract_stream_urls(text: str, base: str = "") -> List[str]:
    found: List[str] = []
    seen = set()

    def add(u: str) -> None:
        u = (u or "").replace("\\/", "/").strip().rstrip("\\")
        if not u or u in seen:
            return
        if u.startswith("//"):
            u = "https:" + u
        elif u.startswith("/") and base:
            u = urljoin(base, u)
        if looks_like_stream(u):
            seen.add(u)
            found.append(u)

    for u in re.findall(r"https?://[^\s\"'<>]+", text or ""):
        add(u)
    for m in re.finditer(
        r'["\'](/stream/[^"\']+)["\']', text or "", re.I
    ):
        add(m.group(1))
    for m in re.finditer(
        r'(?:file|src|source|hls[234]?|image)\s*[:=]\s*["\']([^"\']+)',
        text or "",
        re.I,
    ):
        add(m.group(1))
    return found


# ── HTTP helpers ──────────────────────────────────────────────────

def _session(referer: str = "https://embed69.org/") -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": _UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-419,es;q=0.9,en;q=0.8",
            "Referer": referer,
            "sec-ch-ua": '"Chromium";v="131", "Not_A Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Sec-Fetch-Dest": "iframe",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "cross-site",
        }
    )
    return s


def _get(sess: requests.Session, url: str, referer: str = "") -> str:
    headers = {}
    if referer:
        headers["Referer"] = referer
    r = sess.get(url, headers=headers, timeout=_TIMEOUT, verify=False)
    return r.text or ""


def _file_code_from_url(url: str) -> Optional[str]:
    # /e/CODE  or /v/CODE  or /embed-CODE.html
    m = re.search(r"/(?:e|v|f|d)/([A-Za-z0-9]+)", url)
    if m:
        return m.group(1)
    m = re.search(r"/embed-([A-Za-z0-9]+)", url)
    return m.group(1) if m else None


def _host_family(url: str) -> str:
    h = (urlparse(url).hostname or "").lower()
    if any(h.endswith(m) or h == m for m in STREAMWISH_MIRRORS):
        return "streamwish"
    if any(h.endswith(m) or h == m for m in VIDHIDE_MIRRORS):
        return "vidhide"
    if any(h.endswith(m) or h == m for m in VOE_MIRRORS) or "voe" in h:
        return "voe"
    if any(h.endswith(m) or h == m for m in FILEMOON_MIRRORS):
        return "filemoon"
    if any(h.endswith(m) or h == m for m in FEMBED_MIRRORS) or "fembed" in h or "feurl" in h:
        return "fembed"
    return "generic"


# ── StreamWish: carrera de mirrors + packer ───────────────────────

def resolve_streamwish(url: str, referer: str = "https://embed69.org/") -> List[str]:
    code = _file_code_from_url(url)
    if not code:
        return []
    sess = _session(referer)
    candidates = [f"https://{m}/e/{code}" for m in STREAMWISH_MIRRORS]

    def try_one(u: str) -> List[str]:
        try:
            html = _get(sess, u, referer)
            if len(html) < 800:
                return []
            streams = extract_stream_urls(html, u)
            if streams:
                return streams
            unpacked = unpack_packer(html)
            return extract_stream_urls(unpacked, u) if unpacked else []
        except Exception:
            return []

    # Paralelo: gana el primero con streams (shutdown wait=False para early exit inmediato)
    pool = ThreadPoolExecutor(max_workers=6)
    try:
        futs = {pool.submit(try_one, u): u for u in candidates}
        for fut in as_completed(futs, timeout=_TIMEOUT + 4):
            try:
                streams = fut.result()
            except Exception:
                continue
            if streams:
                for f in futs:
                    f.cancel()
                pool.shutdown(wait=False, cancel_futures=True)
                return streams
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return []


# ── VidHide / Morencius: packer → /stream/ ────────────────────────

def resolve_vidhide(url: str, referer: str = "https://embed69.org/") -> List[str]:
    sess = _session(referer)
    try:
        html = _get(sess, url, referer)
    except Exception:
        return []
    streams = extract_stream_urls(html, url)
    unpacked = unpack_packer(html)
    if unpacked:
        streams.extend(extract_stream_urls(unpacked, url))
        # mirrors del mismo path /stream/...
        for m in re.finditer(r'["\'](/stream/[^"\']+?\.m3u8[^"\']*)["\']', unpacked, re.I):
            path = m.group(1)
            for host in VIDHIDE_MIRRORS:
                streams.append(f"https://{host}{path}")
    return list(dict.fromkeys(streams))


# ── VOE LUT deobfuscation ─────────────────────────────────────────
#
# Algoritmo (ecosistema VOE / reportes públicos):
#   1) César letras: mayúsculas -= 52 (mod-ish via chr), minúsculas -= 84
#   2) Borrar substrings de una tabla LUT fija
#   3) base64 decode
#   4) restar 3 a cada byte
#   5) invertir
#   6) base64 decode → JSON con "source" / file
#
# Si el HTML trae otra tabla LUT inline, se usa esa.

_VOE_LUT_DEFAULT = [
    "$$#??", "??$$#", "#$$??", "??#$$",
    "@#@#@", "#@#@#", "!!!", "###",
]


def _voe_caesar(s: str) -> str:
    out = []
    for ch in s:
        o = ord(ch)
        if 65 <= o <= 90:  # A-Z
            out.append(chr(((o - 65 - 52) % 26) + 65))
        elif 97 <= o <= 122:  # a-z
            out.append(chr(((o - 97 - 84) % 26) + 97))
        else:
            out.append(ch)
    return "".join(out)


def _voe_strip_lut(s: str, lut: Sequence[str]) -> str:
    for token in sorted(lut, key=len, reverse=True):
        if token:
            s = s.replace(token, "")
    return s


def voe_deobfuscate(blob: str, lut: Optional[Sequence[str]] = None) -> Optional[str]:
    try:
        s = _voe_caesar(blob)
        s = _voe_strip_lut(s, lut or _VOE_LUT_DEFAULT)
        raw = base64.b64decode(s + "===")
        raw = bytes((b - 3) & 0xFF for b in raw)
        raw = raw[::-1]
        text = base64.b64decode(raw + b"===").decode("utf-8", errors="replace")
        return text
    except Exception:
        return None


def resolve_voe(url: str, referer: str = "https://embed69.org/") -> List[str]:
    sess = _session(referer)
    # Probar mirrors si el host principal 403
    hosts_to_try = [url]
    code = _file_code_from_url(url)
    if code:
        for m in VOE_MIRRORS:
            alt = f"https://{m}/e/{code}"
            if alt not in hosts_to_try:
                hosts_to_try.append(alt)

    for u in hosts_to_try:
        try:
            html = _get(sess, u, referer)
        except Exception:
            continue
        if len(html) < 500:
            continue
        # m3u8 directo
        streams = extract_stream_urls(html, u)
        if streams:
            return streams
        # LUT table inline
        lut = list(_VOE_LUT_DEFAULT)
        m_lut = re.search(r"(?:lut|LUT)\s*[=:]\s*(\[[^\]]+\])", html)
        if m_lut:
            try:
                lut = json.loads(m_lut.group(1).replace("'", '"'))
            except Exception:
                pass
        # blobs base64 largos
        for m in re.finditer(
            r'["\']([A-Za-z0-9+/=]{60,})["\']', html
        ):
            blob = m.group(1)
            dec = voe_deobfuscate(blob, lut)
            if not dec:
                continue
            streams = extract_stream_urls(dec, u)
            if streams:
                return streams
            # JSON source
            try:
                data = json.loads(dec)
                for key in ("source", "file", "src", "direct_access_url"):
                    val = data.get(key) if isinstance(data, dict) else None
                    if isinstance(val, str) and val.startswith("http"):
                        return [val]
            except Exception:
                if "http" in dec and ".m3u8" in dec:
                    streams = extract_stream_urls(dec, u)
                    if streams:
                        return streams
        unpacked = unpack_packer(html)
        if unpacked:
            streams = extract_stream_urls(unpacked, u)
            if streams:
                return streams
    return []


# ── Filemoon ECDSA attestation (esqueleto funcional) ──────────────
#
# Flujo real observado en clientes:
#   POST /api/videos/access/challenge  → {challenge_id, nonce}
#   POST /api/videos/access/attest     → firma ECDSA P-256 (x,y fijos en algunos clients)
#   POST /api/videos/embed/playback    → payload AES-GCM
#
# Desde datacenter muchos mirrors responden 403/CF. Se deja la
# estructura lista; si el challenge responde 200, se completa el token.

def resolve_filemoon(url: str, referer: str = "https://embed69.org/") -> List[str]:
    sess = _session(referer)
    try:
        html = _get(sess, url, referer)
    except Exception:
        return []
    streams = extract_stream_urls(html, url)
    if streams:
        return streams
    unpacked = unpack_packer(html)
    if unpacked:
        streams = extract_stream_urls(unpacked, url)
        if streams:
            return streams
    # Intento de challenge (si el endpoint existe y no está bloqueado)
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.hostname}"
    code = _file_code_from_url(url)
    if not code:
        return []
    try:
        ch = sess.post(
            f"{origin}/api/videos/access/challenge",
            json={"video_id": code},
            headers={
                "Referer": url,
                "Origin": origin,
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=8,
            verify=False,
        )
        if ch.status_code == 200 and ch.text:
            # Sin clave privada real no firmamos; dejamos rastro en log.
            print(f"[FILEMOON] challenge ok host={parsed.hostname} (attest no implementado)")
    except Exception:
        pass
    return streams


def resolve_fembed(url: str, referer: str = "https://embed69.org/") -> List[str]:
    """Extractor para familia fembed/feurl vía endpoint /api/source/{code}."""
    code = _file_code_from_url(url)
    if not code:
        return []
    parsed = urlparse(url)
    host = parsed.netloc or "fembed.com"
    api_url = f"{parsed.scheme or 'https'}://{host}/api/source/{code}"
    sess = _session(referer)
    try:
        r = sess.post(
            api_url,
            headers={"Referer": url, "X-Requested-With": "XMLHttpRequest"},
            data={"r": referer, "d": host},
            timeout=_TIMEOUT,
        )
        if r.status_code == 200:
            j = r.json()
            if j.get("success") and j.get("data"):
                streams = []
                for item in j["data"]:
                    file_u = item.get("file")
                    if file_u:
                        streams.append(file_u)
                if streams:
                    return streams
    except Exception:
        pass
    return []


# ── Dispatcher ────────────────────────────────────────────────────

def resolve_hoster_url(
    url: str, referer: str = "https://embed69.org/"
) -> List[str]:
    """Resuelve una URL de embed de hoster a lista de m3u8/mp4."""
    if not url or not url.startswith("http"):
        return []
    family = _host_family(url)
    if family == "streamwish":
        return resolve_streamwish(url, referer)
    if family == "vidhide":
        return resolve_vidhide(url, referer)
    if family == "voe":
        return resolve_voe(url, referer)
    if family == "filemoon":
        return resolve_filemoon(url, referer)
    if family == "fembed":
        return resolve_fembed(url, referer)
    # genérico: GET + packer
    sess = _session(referer)
    try:
        html = _get(sess, url, referer)
    except Exception:
        return []
    streams = extract_stream_urls(html, url)
    unpacked = unpack_packer(html)
    if unpacked:
        streams.extend(extract_stream_urls(unpacked, url))
    return list(dict.fromkeys(streams))


# ── Truco .jpg en playlists HLS ───────────────────────────────────
#
# Algunos CDN sirven segmentos MPEG-TS con extensión .jpg para
# esquivar reglas de caché/vídeo. El proxy HLS no debe filtrarlos.
# Usar looks_like_stream() / rewrite que preserve cualquier URI del
# manifiesto, no solo *.ts / *.m3u8.

_SEG_EXT_OK = re.compile(
    r"\.(ts|m4s|mp4|jpg|jpeg|png|html|txt)(\?|$)",
    re.I,
)


def is_hls_segment_uri(uri: str) -> bool:
    """True si la URI de un manifiesto parece segmento o sub-playlist."""
    u = (uri or "").strip()
    if not u or u.startswith("#"):
        return False
    low = u.lower()
    if ".m3u8" in low or "format=m3u8" in low:
        return True
    if _SEG_EXT_OK.search(low):
        return True
    if any(x in low for x in ("/seg-", "segment", "index-v", "frag-")):
        return True
    return False