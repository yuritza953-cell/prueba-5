"""
Provider ES (Latino): videoapi.la

Flujo:
  1) GET /e/movie/{tmdb} | /e/tv/{tmdb}/{s}/{e} | /e/anime/{tmdb}/{s}/{e}
  2) Extrae iframe vimeos.net/embed-XXXX.html?cf=JWT
  3) GET el embed (con cf= preferido; sin cf= a veces packer)
  4) Extrae master.m3u8 (s*.vimeos.net / p*.vimeos.zip)

Necesita content_id numérico TMDB.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import requests
import urllib3

from streams.base import empty_result, ok_result

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_BASE = "https://videoapi.la"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
_TIMEOUT = 18
_VIMEOS_RE = re.compile(
    r"https://vimeos\.net/embed-[A-Za-z0-9]+\.html(?:\?cf=[^\"'\s]*)?",
    re.I,
)
_M3U8_RE = re.compile(
    r"https?://[^\"'\s<>\\]+\.m3u8[^\"'\s<>\\]*",
    re.I,
)


def _tmdb(content_id: str) -> Optional[str]:
    cid = (content_id or "").strip()
    return cid if cid.isdigit() else None


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": _UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-419,es;q=0.9,en;q=0.8",
        }
    )
    return s


def _page_url(kind: str, tmdb: str, season: int = 1, episode: int = 1) -> str:
    if kind == "movie":
        return f"{_BASE}/e/movie/{tmdb}"
    if kind == "anime":
        return f"{_BASE}/e/anime/{tmdb}/{season}/{episode}"
    return f"{_BASE}/e/tv/{tmdb}/{season}/{episode}"


def _fetch_embed_html(sess: requests.Session, embed_url: str) -> str:
    r = sess.get(
        embed_url,
        headers={"Referer": _BASE + "/", "Origin": _BASE},
        timeout=_TIMEOUT,
        verify=False,
    )
    return r.text or ""


def _extract_m3u8(html: str) -> List[str]:
    found: List[str] = []
    seen = set()
    for u in _M3U8_RE.findall(html or ""):
        u = u.replace("\\/", "/").rstrip("\\")
        if u not in seen and "m3u8" in u.lower():
            seen.add(u)
            found.append(u)
    return found


def _resolve_kind(
    kind: str, content_id: str, season: int = 1, episode: int = 1
) -> Dict[str, Any]:
    tmdb = _tmdb(content_id)
    if not tmdb:
        return empty_result("videoapi", error="videoapi_needs_tmdb", ref_url=_BASE + "/")

    sess = _session()
    page = _page_url(kind, tmdb, season, episode)
    print(f"[VIDEOAPI] resolve {kind} tmdb={tmdb}" + (f" S{season}E{episode}" if kind != "movie" else ""))
    try:
        r = sess.get(page, timeout=_TIMEOUT)
    except Exception as exc:
        print(f"[VIDEOAPI] page fail: {exc}")
        return empty_result("videoapi", error="videoapi_page_error", ref_url=_BASE + "/")

    if r.status_code == 400:
        return empty_result("videoapi", error="videoapi_bad_id", ref_url=page)
    if r.status_code >= 400:
        return empty_result(
            "videoapi", error=f"videoapi_http_{r.status_code}", ref_url=page
        )

    html = r.text or ""
    embeds = _VIMEOS_RE.findall(html)
    if not embeds:
        # a veces el script tiene el token partido
        m = re.search(
            r"vimeos\.net/embed-([A-Za-z0-9]+)\.html",
            html,
            re.I,
        )
        if m:
            embeds = [f"https://vimeos.net/embed-{m.group(1)}.html"]
    if not embeds:
        print("[VIDEOAPI] no vimeos embed in page")
        return empty_result("videoapi", error="videoapi_no_embed", ref_url=page)

    # Preferir URL con cf= (en pruebas devolvió el player completo)
    embeds_sorted = sorted(embeds, key=lambda u: (0 if "?cf=" in u else 1, len(u)))
    streams: List[str] = []
    last_embed = embeds_sorted[0]

    for emb in embeds_sorted[:2]:
        last_embed = emb
        try:
            ehtml = _fetch_embed_html(sess, emb)
        except Exception as exc:
            print(f"[VIDEOAPI] embed fail: {exc}")
            continue
        streams = _extract_m3u8(ehtml)
        if streams:
            break
        # Si trae cf= y falló, probar sin cf (packer / variante)
        if "?cf=" in emb:
            bare = emb.split("?cf=")[0]
            try:
                ehtml = _fetch_embed_html(sess, bare)
                streams = _extract_m3u8(ehtml)
                if streams:
                    last_embed = bare
                    break
            except Exception:
                pass

    if not streams:
        print("[VIDEOAPI] no m3u8 in vimeos embed")
        return empty_result("videoapi", error="videoapi_no_m3u8", ref_url=last_embed)

    print(f"[VIDEOAPI] OK streams={len(streams)} host={streams[0].split('/')[2]}")
    return ok_result(
        "videoapi",
        streams[0],
        stream_type="hls",
        candidates=streams,
        ref_url="https://vimeos.net/",
        embed_url=last_embed,
    )


class VideoApiProvider:
    name = "videoapi"
    langs = ("es",)

    def resolve_movie(self, content_id: str) -> Dict[str, Any]:
        return _resolve_kind("movie", content_id)

    def resolve_tv(
        self, content_id: str, season: int = 1, episode: int = 1
    ) -> Dict[str, Any]:
        # TV primero; si falla, intentar ruta anime (mismo catálogo TMDB)
        data = _resolve_kind("tv", content_id, season, episode)
        if data.get("stream_url"):
            return data
        anime = _resolve_kind("anime", content_id, season, episode)
        if anime.get("stream_url"):
            return anime
        return data