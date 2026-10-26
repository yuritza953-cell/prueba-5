"""
Provider ES: Cuevana (cuevana3) — latino / sub.

Estrategia:
  1) Obtener título TMDB
  2) Búsqueda /peliculas/?s= o /?s=
  3) Parseo de .btn con data-tr o enlaces de reproductores
  4) Resolución vía hosters (StreamWish, VidHide, Filemoon, VOE, Fembed)
"""
from __future__ import annotations

import base64
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urljoin

import requests
import urllib3

from streams.base import empty_result, ok_result
from streams.providers.hosters import resolve_hoster_url

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_MIRRORS = [
    "https://cuevana3.ch",
    "https://cuevana.biz",
]
_TIMEOUT = 5

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def _headers(ref: str = "") -> Dict[str, str]:
    h = {
        "User-Agent": _UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-419,es;q=0.9,en;q=0.5",
    }
    if ref:
        h["Referer"] = ref
    return h


def _tmdb_title(tmdb_id: str, is_tv: bool) -> Optional[str]:
    key = (os.environ.get("TMDB_API_KEY") or os.environ.get("TMDB_KEY") or "").strip()
    if not tmdb_id.isdigit() or not key:
        return None
    kind = "tv" if is_tv else "movie"
    headers = {"Accept": "application/json"}
    if key.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {key}"
        url = f"https://api.themoviedb.org/3/{kind}/{tmdb_id}?language=es-MX"
    else:
        url = f"https://api.themoviedb.org/3/{kind}/{tmdb_id}?api_key={key}&language=es-MX"
    try:
        r = requests.get(url, headers=headers, timeout=8)
        j = r.json()
        return j.get("title") or j.get("name") or j.get("original_title")
    except Exception:
        return None


def _extract_embeds(html: str, base_url: str) -> List[str]:
    """Parseo de data-tr de los .btn o enlaces de reproductores."""
    embeds: List[str] = []
    # 1. data-tr en .btn o elementos similares
    for m in re.finditer(r'class=["\'][^"\']*\bbtn\b[^"\']*["\'][^>]*data-tr=["\']([^"\']+)["\']', html, re.I):
        tr = m.group(1).strip()
        if tr.startswith("http"):
            embeds.append(tr)
        elif tr.startswith("//"):
            embeds.append("https:" + tr)
        else:
            try:
                dec = base64.b64decode(tr).decode("utf-8", errors="ignore").strip()
                if dec.startswith("http"):
                    embeds.append(dec)
            except Exception:
                pass

    # 2. Otros data-src o iframes
    for m in re.finditer(r'(?:data-src|data-video|src)=["\']([^"\']+)["\']', html, re.I):
        u = m.group(1).strip()
        if any(h in u.lower() for h in ("streamwish", "vidhide", "filemoon", "voe", "fembed", "feurl", "dood")):
            if u.startswith("//"):
                u = "https:" + u
            elif u.startswith("/"):
                u = urljoin(base_url, u)
            embeds.append(u)

    return list(dict.fromkeys(embeds))


def _resolve(content_id: str, is_tv: bool = False, season: int = 1, episode: int = 1) -> Dict[str, Any]:
    title = _tmdb_title(content_id, is_tv) or content_id
    sess = requests.Session()
    sess.headers.update(_headers())

    for base in _MIRRORS:
        search_paths = [
            f"{base}/peliculas/?s={quote(title)}",
            f"{base}/?s={quote(title)}",
        ]
        post_url = None
        for s_url in search_paths:
            try:
                r = sess.get(s_url, timeout=_TIMEOUT, verify=False)
                if r.status_code == 200:
                    for m in re.finditer(r'href=["\']([^"\']*(?:pelicula|serie|episodio)/[^"\']+)["\']', r.text, re.I):
                        href = m.group(1)
                        if "wp-" not in href:
                            post_url = urljoin(base, href)
                            break
                if post_url:
                    break
            except Exception:
                continue

        if not post_url:
            continue

        try:
            r = sess.get(post_url, headers=_headers(base + "/"), timeout=_TIMEOUT, verify=False)
            if r.status_code != 200:
                continue
            embeds = _extract_embeds(r.text, post_url)
            for emb in embeds:
                streams = resolve_hoster_url(emb, referer=post_url)
                if streams:
                    return ok_result("cuevana", streams[0], candidates=streams, ref_url=post_url)
        except Exception:
            continue

    return empty_result("cuevana", error="no_stream")


class CuevanaProvider:
    name = "cuevana"
    langs = ("es", "es-MX", "sub")

    def resolve_movie(self, content_id: str) -> Dict[str, Any]:
        return _resolve(content_id, is_tv=False)

    def resolve_tv(self, content_id: str, season: int = 1, episode: int = 1) -> Dict[str, Any]:
        return _resolve(content_id, is_tv=True, season=season, episode=episode)
