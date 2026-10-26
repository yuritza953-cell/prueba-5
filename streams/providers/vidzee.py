"""
Provider EN: VidZee — m3u8 en claro con e=0 (sin WASM).

  GET https://core.vidzee.wtf/streams/movie/{tmdb}?s={server}&e=0
  GET https://core.vidzee.wtf/streams/tv/{tmdb}/{s}/{e}?s={server}&e=0
  Referer/Origin: https://player.vidzee.wtf/
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests
import urllib3

from streams.base import empty_result, ok_result

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_API = "https://core.vidzee.wtf"
_PLAYER = "https://player.vidzee.wtf"
_SERVERS = ("dcloud", "tik", "ipcloud")
_TIMEOUT = 14


def _headers() -> Dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Referer": f"{_PLAYER}/",
        "Origin": _PLAYER,
    }


def _tmdb(content_id: str) -> Optional[str]:
    cid = (content_id or "").strip()
    return cid if cid.isdigit() else None


def _resolve(
    tmdb: str,
    *,
    season: Optional[int] = None,
    episode: Optional[int] = None,
) -> Dict[str, Any]:
    is_tv = season is not None
    label = f"tv {tmdb} S{season}E{episode}" if is_tv else f"movie {tmdb}"
    print(f"[VIDZEE] resolve {label}")

    candidates: List[str] = []
    primary = None
    for sr in _SERVERS:
        if is_tv:
            path = f"/streams/tv/{tmdb}/{int(season)}/{int(episode)}"
        else:
            path = f"/streams/movie/{tmdb}"
        url = f"{_API}{path}?s={sr}&e=0"
        try:
            r = requests.get(url, headers=_headers(), timeout=_TIMEOUT, verify=False)
            if r.status_code != 200:
                continue
            data = r.json()
            u = (data.get("url") or "").strip()
            if u.startswith("http"):
                candidates.append(u)
                if primary is None:
                    primary = u
                    print(f"[VIDZEE] OK server={sr}")
        except Exception as exc:
            print(f"[VIDZEE] {sr} fail: {exc}")

    if not primary:
        return empty_result("vidzee", error="vidzee_no_streams", ref_url=_PLAYER + "/")

    return ok_result(
        "vidzee",
        primary,
        stream_type="hls",
        candidates=list(dict.fromkeys(candidates)),
        ref_url=_PLAYER + "/",
    )


class VidZeeProvider:
    name = "vidzee"
    langs = ("en",)

    def resolve_movie(self, content_id: str) -> Dict[str, Any]:
        tmdb = _tmdb(content_id)
        if not tmdb:
            return empty_result(self.name, error="vidzee_needs_tmdb", ref_url=_PLAYER + "/")
        return _resolve(tmdb)

    def resolve_tv(
        self, content_id: str, season: int = 1, episode: int = 1
    ) -> Dict[str, Any]:
        tmdb = _tmdb(content_id)
        if not tmdb:
            return empty_result(self.name, error="vidzee_needs_tmdb", ref_url=_PLAYER + "/")
        return _resolve(tmdb, season=season, episode=episode)