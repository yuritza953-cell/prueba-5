"""
Provider EN: VidApi (vaplayer.ru / streamdata.vaplayer.ru).

API pública usada por CinePro:
  GET https://streamdata.vaplayer.ru/api.php?tmdb={id}&type=movie|tv[&season=&episode=]
  Headers: Referer/Origin = https://brightpathsignals.com/

Solo cadena inglés (audio Original / eng). NO mezclar con ES.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests
import urllib3

from streams.base import empty_result, ok_result

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_API = "https://streamdata.vaplayer.ru/api.php"
_REF = "https://brightpathsignals.com/"
_TIMEOUT = 20


def _headers() -> Dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Referer": _REF,
        "Origin": "https://brightpathsignals.com",
        "Accept": "*/*",
        "Accept-Language": "es-419,es;q=0.9,en;q=0.8",
    }


def _tmdb(content_id: str) -> Optional[str]:
    cid = (content_id or "").strip()
    if cid.isdigit():
        return cid
    return None


def _infer_type(url: str) -> str:
    low = (url or "").lower().split("?", 1)[0]
    if low.endswith((".mp4", ".mkv", ".webm")):
        return "mp4"
    return "hls"


def _resolve(
    tmdb: str,
    *,
    is_tv: bool = False,
    season: int = 1,
    episode: int = 1,
) -> Dict[str, Any]:
    params: Dict[str, str] = {
        "tmdb": tmdb,
        "type": "tv" if is_tv else "movie",
    }
    if is_tv:
        params["season"] = str(int(season))
        params["episode"] = str(int(episode))

    label = f"tv {tmdb} S{season}E{episode}" if is_tv else f"movie {tmdb}"
    print(f"[VIDAPI] resolve {label}")

    try:
        r = requests.get(
            _API,
            params=params,
            headers=_headers(),
            timeout=_TIMEOUT,
            verify=False,
        )
    except Exception as exc:
        print(f"[VIDAPI] request fail: {exc}")
        return empty_result("vidapi", error="vidapi_request_error", ref_url=_REF)

    if r.status_code >= 400:
        return empty_result(
            "vidapi", error=f"vidapi_http_{r.status_code}", ref_url=_REF
        )

    try:
        payload = r.json()
    except Exception:
        return empty_result("vidapi", error="vidapi_bad_json", ref_url=_REF)

    if str(payload.get("status_code")) != "200" or not payload.get("data"):
        return empty_result(
            "vidapi",
            error=f"vidapi_status_{payload.get('status_code')}",
            ref_url=_REF,
        )

    data = payload["data"]
    urls: List[str] = []
    for u in data.get("stream_urls") or []:
        if isinstance(u, str) and u.startswith("http"):
            urls.append(u)
        elif isinstance(u, dict):
            cand = u.get("url") or u.get("file") or u.get("src")
            if isinstance(cand, str) and cand.startswith("http"):
                urls.append(cand)

    urls = list(dict.fromkeys(urls))
    if not urls:
        return empty_result("vidapi", error="vidapi_no_streams", ref_url=_REF)

    # Prefer first HLS-looking URL
    primary = urls[0]
    for u in urls:
        if ".m3u8" in u.lower() or "/pl/" in u.lower():
            primary = u
            break

    print(f"[VIDAPI] OK streams={len(urls)} file={data.get('file_name')}")
    return ok_result(
        "vidapi",
        primary,
        stream_type=_infer_type(primary),
        candidates=urls,
        ref_url=_REF,
        file_name=data.get("file_name"),
        title=data.get("title"),
        imdb_id=data.get("imdb_id"),
    )


class VidApiProvider:
    name = "vidapi"
    langs = ("en",)

    def resolve_movie(self, content_id: str) -> Dict[str, Any]:
        tmdb = _tmdb(content_id)
        if not tmdb:
            return empty_result(self.name, error="vidapi_needs_tmdb", ref_url=_REF)
        return _resolve(tmdb, is_tv=False)

    def resolve_tv(
        self, content_id: str, season: int = 1, episode: int = 1
    ) -> Dict[str, Any]:
        tmdb = _tmdb(content_id)
        if not tmdb:
            return empty_result(self.name, error="vidapi_needs_tmdb", ref_url=_REF)
        return _resolve(tmdb, is_tv=True, season=season, episode=episode)