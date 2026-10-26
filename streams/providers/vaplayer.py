"""
Provider EN: VaPlayer (streamdata.vaplayer.ru).

Devuelve HLS master.m3u8 directo por IMDb id.
Necesita content_id tipo ttXXXXXXX (IMDb).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests
import urllib3

from streams.base import empty_result, ok_result

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_API = "https://streamdata.vaplayer.ru/api.php"
_REF = "https://nextgencloudfabric.com/"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
_TIMEOUT = 18


def _imdb(content_id: str) -> Optional[str]:
    cid = (content_id or "").strip()
    if cid.startswith("tt") and cid[2:].isdigit():
        return cid
    return None


def _fetch(imdb: str, media: str, season: int = 1, episode: int = 1) -> Dict[str, Any]:
    params: Dict[str, Any] = {"imdb": imdb, "type": media}
    if media == "tv":
        params["season"] = season
        params["episode"] = episode
    r = requests.get(
        _API,
        params=params,
        headers={
            "User-Agent": _UA,
            "Accept": "application/json,text/plain,*/*",
            "Referer": _REF,
            "Origin": _REF.rstrip("/"),
        },
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json() if r.text else {}


def _pick_urls(payload: Dict[str, Any]) -> List[str]:
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return []
    raw = data.get("stream_urls") or []
    out: List[str] = []
    for u in raw:
        if isinstance(u, str) and u.startswith("http") and (
            ".m3u8" in u.lower() or ".mp4" in u.lower()
        ):
            out.append(u)
    return out


class VaPlayerProvider:
    name = "vaplayer"
    langs = ("en",)

    def resolve_movie(self, content_id: str) -> Dict[str, Any]:
        imdb = _imdb(content_id)
        if not imdb:
            return empty_result(self.name, error="vaplayer_needs_imdb", ref_url=_REF)
        try:
            print(f"[VAPLAYER] resolve movie {imdb}")
            payload = _fetch(imdb, "movie")
            urls = _pick_urls(payload)
            if not urls:
                return empty_result(self.name, error="vaplayer_no_streams", ref_url=_REF)
            print(f"[VAPLAYER] movie {imdb} streams={len(urls)}")
            return ok_result(
                self.name,
                urls[0],
                candidates=urls,
                ref_url=_REF,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[VAPLAYER] movie fail: {exc}")
            return empty_result(self.name, error="vaplayer_error", ref_url=_REF)

    def resolve_tv(
        self, content_id: str, season: int = 1, episode: int = 1
    ) -> Dict[str, Any]:
        imdb = _imdb(content_id)
        if not imdb:
            return empty_result(self.name, error="vaplayer_needs_imdb", ref_url=_REF)
        try:
            print(f"[VAPLAYER] resolve tv {imdb} S{season}E{episode}")
            payload = _fetch(imdb, "tv", season, episode)
            urls = _pick_urls(payload)
            if not urls:
                return empty_result(self.name, error="vaplayer_no_streams", ref_url=_REF)
            print(f"[VAPLAYER] tv {imdb} streams={len(urls)}")
            return ok_result(
                self.name,
                urls[0],
                candidates=urls,
                ref_url=_REF,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[VAPLAYER] tv fail: {exc}")
            return empty_result(self.name, error="vaplayer_error", ref_url=_REF)