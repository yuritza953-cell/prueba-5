"""
Provider EN: VixSrc (vixsrc.to).

Flujo (igual que CinePro):
  1) GET /api/movie/{tmdb}  o  /api/tv/{tmdb}/{s}/{e}
  2) GET {BASE}{src}  → HTML con token / expires / url
  3) master = {url}?token=...&expires=...&h=1

Audio típico: eng / ita. Solo cadena inglés.
"""
from __future__ import annotations

import re
import time
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import requests
import urllib3

from streams.base import empty_result, ok_result

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_BASE = "https://vixsrc.to"
_TIMEOUT = 18


def _headers(referer: str = _BASE + "/") -> Dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "es-419,es;q=0.9,en;q=0.8",
        "Referer": referer,
        "Origin": _BASE,
    }


def _tmdb(content_id: str) -> Optional[str]:
    cid = (content_id or "").strip()
    return cid if cid.isdigit() else None


def _api_url(tmdb: str, season: Optional[int], episode: Optional[int]) -> str:
    if season is not None and episode is not None:
        return f"{_BASE}/api/tv/{tmdb}/{int(season)}/{int(episode)}"
    return f"{_BASE}/api/movie/{tmdb}"


def _extract_token_data(html: str) -> Optional[Dict[str, str]]:
    token = re.search(r'token["\']\s*:\s*["\']([^"\']+)', html)
    expires = re.search(r'expires["\']\s*:\s*["\']([^"\']+)', html)
    url = re.search(r'url\s*:\s*["\']([^"\']+)', html)
    if not (token and expires and url):
        return None
    exp = expires.group(1)
    try:
        # expires suele ser unix seconds
        if int(exp) * 1000 - 60_000 < int(time.time() * 1000):
            return None
    except ValueError:
        pass
    return {
        "token": token.group(1),
        "expires": exp,
        "playlist": url.group(1),
    }


def _resolve(
    tmdb: str,
    *,
    season: Optional[int] = None,
    episode: Optional[int] = None,
) -> Dict[str, Any]:
    page = _api_url(tmdb, season, episode)
    label = (
        f"tv {tmdb} S{season}E{episode}"
        if season is not None
        else f"movie {tmdb}"
    )
    print(f"[VIXSRC] resolve {label}")

    sess = requests.Session()
    try:
        r = sess.get(page, headers=_headers(), timeout=_TIMEOUT, verify=False)
    except Exception as exc:
        print(f"[VIXSRC] api fail: {exc}")
        return empty_result("vixsrc", error="vixsrc_api_error", ref_url=_BASE + "/")

    if r.status_code != 200:
        return empty_result(
            "vixsrc", error=f"vixsrc_http_{r.status_code}", ref_url=page
        )

    sublink = None
    try:
        data = r.json()
        if isinstance(data, dict):
            sublink = data.get("src") or data.get("url") or data.get("embed")
    except Exception:
        # a veces devuelve HTML directo
        if "token" in (r.text or ""):
            token_data = _extract_token_data(r.text)
            if token_data:
                pl = token_data["playlist"]
                if not pl.startswith("http"):
                    pl = urljoin(_BASE + "/", pl)
                sep = "&" if "?" in pl else "?"
                master = f"{pl}{sep}token={token_data['token']}&expires={token_data['expires']}&h=1"
                print(f"[VIXSRC] OK master from api html")
                return ok_result(
                    "vixsrc", master, stream_type="hls", candidates=[master], ref_url=page
                )
        return empty_result("vixsrc", error="vixsrc_bad_json", ref_url=page)

    if not sublink:
        return empty_result("vixsrc", error="vixsrc_no_src", ref_url=page)

    embed_url = sublink if str(sublink).startswith("http") else urljoin(_BASE + "/", str(sublink))
    try:
        r2 = sess.get(
            embed_url, headers=_headers(page), timeout=_TIMEOUT, verify=False
        )
    except Exception as exc:
        print(f"[VIXSRC] embed fail: {exc}")
        return empty_result("vixsrc", error="vixsrc_embed_error", ref_url=page)

    if r2.status_code != 200:
        return empty_result(
            "vixsrc", error=f"vixsrc_embed_{r2.status_code}", ref_url=page
        )

    token_data = _extract_token_data(r2.text or "")
    if not token_data:
        return empty_result("vixsrc", error="vixsrc_no_token", ref_url=page)

    pl = token_data["playlist"]
    if not pl.startswith("http"):
        pl = urljoin(_BASE + "/", pl)
    sep = "&" if "?" in pl else "?"
    master = f"{pl}{sep}token={token_data['token']}&expires={token_data['expires']}&h=1"
    print(f"[VIXSRC] OK master")
    return ok_result(
        "vixsrc",
        master,
        stream_type="hls",
        candidates=[master],
        ref_url=page,
    )


class VixSrcProvider:
    name = "vixsrc"
    langs = ("en",)

    def resolve_movie(self, content_id: str) -> Dict[str, Any]:
        tmdb = _tmdb(content_id)
        if not tmdb:
            return empty_result(self.name, error="vixsrc_needs_tmdb", ref_url=_BASE + "/")
        return _resolve(tmdb)

    def resolve_tv(
        self, content_id: str, season: int = 1, episode: int = 1
    ) -> Dict[str, Any]:
        tmdb = _tmdb(content_id)
        if not tmdb:
            return empty_result(self.name, error="vixsrc_needs_tmdb", ref_url=_BASE + "/")
        return _resolve(tmdb, season=season, episode=episode)