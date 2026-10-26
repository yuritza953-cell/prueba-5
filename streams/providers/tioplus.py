"""
Provider ES: TioPlus — castellano / sub.

Estrategia:
  1) Búsqueda por título TMDB en tioplus (?s=)
  2) Extracción de embed tapecontent (streamtape) y hosters
  3) Resolución a stream directo / HLS / MP4
"""
from __future__ import annotations

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
    "https://tioplus.app",
    "https://tioplus.net",
    "https://tioplus.vip",
]
_TIMEOUT = 12

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def _headers(ref: str = "") -> Dict[str, str]:
    h = {
        "User-Agent": _UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.5",
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
        url = f"https://api.themoviedb.org/3/{kind}/{tmdb_id}?language=es-ES"
    else:
        url = f"https://api.themoviedb.org/3/{kind}/{tmdb_id}?api_key={key}&language=es-ES"
    try:
        r = requests.get(url, headers=headers, timeout=8)
        j = r.json()
        return j.get("title") or j.get("name") or j.get("original_title")
    except Exception:
        return None


def _extract_tapecontent(html: str, base_url: str) -> List[str]:
    """Extrae enlaces de tapecontent / streamtape y hosters asociados."""
    embeds: List[str] = []
    # 1. tapecontent / streamtape embeds
    for m in re.finditer(r'(https?://(?:tapecontent\.net|streamtape\.com)/[e|v]/[A-Za-z0-9]+)', html, re.I):
        embeds.append(m.group(1))

    # 2. Otros hosters o iframes
    for m in re.finditer(r'<iframe[^>]+src=["\']([^"\']+)["\']', html, re.I):
        src = m.group(1)
        if any(x in src.lower() for x in ("tapecontent", "streamtape", "streamwish", "vidhide", "filemoon", "voe")):
            if src.startswith("//"):
                src = "https:" + src
            elif src.startswith("/"):
                src = urljoin(base_url, src)
            embeds.append(src)

    return list(dict.fromkeys(embeds))


def _resolve_tapecontent_direct(url: str, referer: str = "") -> Optional[str]:
    """Resuelve token directo de tapecontent/streamtape si está disponible en HTML."""
    try:
        s = requests.Session()
        s.headers.update(_headers(referer))
        r = s.get(url, timeout=_TIMEOUT, verify=False)
        if r.status_code == 200:
            m = re.search(r'id=["\']robotlink["\'][^>]*>([^<]+)<', r.text)
            if m:
                token = m.group(1).strip()
                if token.startswith("//"):
                    return "https:" + token
                if token.startswith("http"):
                    return token
    except Exception:
        pass
    return None


def _resolve(content_id: str, is_tv: bool = False, season: int = 1, episode: int = 1) -> Dict[str, Any]:
    title = _tmdb_title(content_id, is_tv) or content_id
    sess = requests.Session()
    sess.headers.update(_headers())

    for base in _MIRRORS:
        search_url = f"{base}/?s={quote(title)}"
        post_url = None
        try:
            r = sess.get(search_url, timeout=_TIMEOUT, verify=False)
            if r.status_code == 200:
                for m in re.finditer(r'href=["\']([^"\']*(?:pelicula|series?|episodio)/[^"\']+)["\']', r.text, re.I):
                    href = m.group(1)
                    if "wp-" not in href:
                        post_url = urljoin(base, href)
                        break
        except Exception:
            continue

        if not post_url:
            continue

        try:
            r = sess.get(post_url, headers=_headers(base + "/"), timeout=_TIMEOUT, verify=False)
            if r.status_code != 200:
                continue

            embeds = _extract_tapecontent(r.text, post_url)
            for emb in embeds:
                # 1. Probar extracción tapecontent directo
                if "tapecontent" in emb or "streamtape" in emb:
                    direct = _resolve_tapecontent_direct(emb, referer=post_url)
                    if direct:
                        return ok_result("tioplus", direct, stream_type="mp4", ref_url=post_url)

                # 2. Hosters generales
                streams = resolve_hoster_url(emb, referer=post_url)
                if streams:
                    return ok_result("tioplus", streams[0], candidates=streams, ref_url=post_url)
        except Exception:
            continue

    return empty_result("tioplus", error="no_stream")


class TioPlusProvider:
    name = "tioplus"
    langs = ("es", "es-ES", "sub")

    def resolve_movie(self, content_id: str) -> Dict[str, Any]:
        return _resolve(content_id, is_tv=False)

    def resolve_tv(self, content_id: str, season: int = 1, episode: int = 1) -> Dict[str, Any]:
        return _resolve(content_id, is_tv=True, season=season, episode=episode)
