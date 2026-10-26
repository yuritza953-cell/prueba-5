"""
Provider ES: embed69.org (SoloLatino ecosystem).

1) GET https://embed69.org/f/{imdb}  (tv: {imdb}-{s:02d}x{ep:02d})
   Referer: https://sololatino.net/
2) Minar PoW: SHA256(challenge+nonce) empieza con N ceros
3) key = SHA256(challenge+nonce+salt)
4) AES-256-CBC de cada link (IV 16 bytes + ciphertext)
5) Resolver hosters (morencius/vidhide packer → m3u8)

Requiere openssl en PATH (imagen Docker ya lo suele tener).
"""
from __future__ import annotations

import base64
import hashlib
import re
import subprocess
from typing import Any, Dict, List, Optional, Tuple

import requests
import urllib3

from streams.base import empty_result, ok_result
from streams.providers.hosters import resolve_hoster_url

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_BASE = "https://embed69.org"
_REF = "https://sololatino.net/"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
_TIMEOUT = 8
_MAX_NONCE = 5_000_000

_PACKER_RE = re.compile(
    r"eval\(function\(p,a,c,k,e,(?:d|r)\).*?\}\('((?:\\'|[^'])*)',(\d+),(\d+),'((?:\\'|[^'])*)'\.split\('\|'\)",
    re.DOTALL,
)

# Prefer hosters that usually yield HLS via packer
_HOSTER_PRIORITY = ("vidhide", "streamwish", "voe", "filemoon", "doodstream")


def _imdb(content_id: str) -> Optional[str]:
    cid = (content_id or "").strip()
    if cid.startswith("tt") and cid[2:].isdigit():
        return cid
    return None


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _sha256_bytes(s: str) -> bytes:
    return hashlib.sha256(s.encode()).digest()


def _solve_pow(challenge: str, difficulty: int, salt: str) -> Optional[bytes]:
    prefix = "0" * int(difficulty)
    for nonce in range(_MAX_NONCE):
        if _sha256_hex(f"{challenge}{nonce}").startswith(prefix):
            return _sha256_bytes(f"{challenge}{nonce}{salt}")
    return None


def _decrypt_aes(b64: str, key: bytes) -> Optional[str]:
    try:
        raw = base64.b64decode(b64)
        if len(raw) < 17:
            return None
        iv, ct = raw[:16], raw[16:]
        p = subprocess.run(
            [
                "openssl",
                "enc",
                "-aes-256-cbc",
                "-d",
                "-K",
                key[:32].hex(),
                "-iv",
                iv.hex(),
            ],
            input=ct,
            capture_output=True,
            timeout=5,
        )
        if p.returncode != 0 or not p.stdout:
            return None
        pt = p.stdout
        pad = pt[-1]
        if 1 <= pad <= 16 and all(b == pad for b in pt[-pad:]):
            pt = pt[:-pad]
        text = pt.decode("utf-8", errors="replace").strip()
        return text if text.startswith("http") else None
    except Exception:
        return None


def _base_n(n: int, base: int) -> str:
    chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if n == 0:
        return "0"
    s = ""
    while n:
        s = chars[n % base] + s
        n //= base
    return s


def _unpack_packer(html: str) -> str:
    parts: List[str] = []
    for m in _PACKER_RE.finditer(html or ""):
        try:
            payload, a, c, kstr = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
            keys = kstr.split("|")
            p = payload
            while c:
                c -= 1
                if c < len(keys) and keys[c]:
                    p = re.sub(r"\b" + re.escape(_base_n(c, a)) + r"\b", keys[c], p)
            parts.append(p)
        except Exception:
            continue
    return "\n".join(parts)


def _m3u8_from_text(text: str, base: str = "") -> List[str]:
    found: List[str] = []
    seen = set()
    for u in re.findall(r'https?://[^\s"\'<>\\]+', text or ""):
        u = u.replace("\\/", "/").rstrip("\\")
        if ".m3u8" in u.lower() and u not in seen:
            seen.add(u)
            found.append(u)
    for m in re.finditer(
        r'["\'](/stream/[^"\']+\.m3u8[^"\']*)["\']', text or "", re.I
    ):
        path = m.group(1).replace("\\/", "/")
        if base:
            from urllib.parse import urljoin

            abs_u = urljoin(base, path)
            if abs_u not in seen:
                seen.add(abs_u)
                found.append(abs_u)
    return found


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": _UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-419,es;q=0.9,en;q=0.8",
            "Referer": _REF,
        }
    )
    return s


def _page_path(imdb: str, season: Optional[int], episode: Optional[int]) -> str:
    if season is not None and episode is not None:
        return f"{_BASE}/f/{imdb}-{int(season):02d}x{int(episode):02d}"
    return f"{_BASE}/f/{imdb}"


def _decrypt_embeds(html: str) -> List[Tuple[str, str]]:
    m_c = re.search(r"POW_CHALLENGE\s*=\s*['\"]([^'\"]+)", html)
    m_d = re.search(r"POW_DIFFICULTY\s*=\s*(\d+)", html)
    m_s = re.search(r"POW_SALT\s*=\s*['\"]([^'\"]+)", html)
    if not (m_c and m_d and m_s):
        return []
    key = _solve_pow(m_c.group(1), int(m_d.group(1)), m_s.group(1))
    if not key:
        print("[EMBED69] pow fail")
        return []
    out: List[Tuple[str, str]] = []
    for name, link in re.findall(
        r'\{"servername":"([^"]+)","link":"([^"]+)","type":"video"\}', html
    ):
        dec = _decrypt_aes(link.replace("\\/", "/"), key)
        if dec:
            out.append((name.lower(), dec))
    return out


def _resolve_hoster(sess: requests.Session, name: str, url: str) -> List[str]:
    # StreamWish / VidHide / VOE / Filemoon vía módulo hosters (mirrors + packer + LUT)
    try:
        streams = resolve_hoster_url(url, referer=_BASE + "/")
        if streams:
            return streams
    except Exception as exc:
        print(f"[EMBED69] hosters module {name}: {exc}")
    # Fallback local (packer simple)
    try:
        r = sess.get(
            url,
            headers={
                "Referer": _BASE + "/",
                "Origin": _BASE,
                "Sec-Fetch-Dest": "iframe",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "cross-site",
            },
            timeout=_TIMEOUT,
            verify=False,
        )
    except Exception as exc:
        print(f"[EMBED69] hoster {name} fail: {exc}")
        return []
    html = r.text or ""
    streams = _m3u8_from_text(html, url)
    if streams:
        return streams
    unpacked = _unpack_packer(html)
    if unpacked:
        streams = _m3u8_from_text(unpacked, url)
    return list(dict.fromkeys(streams))


def _resolve(imdb: str, season: Optional[int] = None, episode: Optional[int] = None) -> Dict[str, Any]:
    path = _page_path(imdb, season, episode)
    label = f"{imdb}" + (f" S{season}E{episode}" if season else "")
    print(f"[EMBED69] resolve {label}")
    sess = _session()
    try:
        r = sess.get(path, timeout=_TIMEOUT)
    except Exception as exc:
        print(f"[EMBED69] page fail: {exc}")
        return empty_result("embed69", error="embed69_page_error", ref_url=_REF)

    if r.status_code >= 400 or "POW_CHALLENGE" not in (r.text or ""):
        return empty_result("embed69", error="embed69_no_pow", ref_url=path)

    embeds = _decrypt_embeds(r.text)
    if not embeds:
        return empty_result("embed69", error="embed69_no_links", ref_url=path)

    # Ordenar por prioridad de hoster
    def prio(item: Tuple[str, str]) -> int:
        name = item[0]
        try:
            return _HOSTER_PRIORITY.index(name)
        except ValueError:
            return 99

    embeds = sorted(embeds, key=prio)
    print(f"[EMBED69] {len(embeds)} embeds decrypted")

    all_streams: List[str] = []
    for name, url in embeds[:8]:
        streams = _resolve_hoster(sess, name, url)
        if streams:
            print(f"[EMBED69] hoster {name} → {len(streams)} streams")
            all_streams.extend(streams)
            break

    if not all_streams:
        return empty_result("embed69", error="embed69_no_m3u8", ref_url=path)

    all_streams = list(dict.fromkeys(all_streams))
    return ok_result(
        "embed69",
        all_streams[0],
        stream_type="hls",
        candidates=all_streams,
        ref_url=_REF,
    )


class Embed69Provider:
    name = "embed69"
    langs = ("es",)

    def resolve_movie(self, content_id: str) -> Dict[str, Any]:
        imdb = _imdb(content_id)
        if not imdb:
            return empty_result(self.name, error="embed69_needs_imdb", ref_url=_REF)
        return _resolve(imdb)

    def resolve_tv(
        self, content_id: str, season: int = 1, episode: int = 1
    ) -> Dict[str, Any]:
        imdb = _imdb(content_id)
        if not imdb:
            return empty_result(self.name, error="embed69_needs_imdb", ref_url=_REF)
        return _resolve(imdb, season, episode)