"""
Provider EN: VidLink.pro

1) GET enc-dec.app/api/enc-vidlink?text={tmdbId}
2) GET vidlink.pro/api/b/movie|{tv}/... → qualities MP4

Necesita content_id numérico TMDB (no tt...).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import requests
import urllib3

from streams.base import empty_result, ok_result

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_ENC = "https://enc-dec.app/api/enc-vidlink"
_API_MOVIE = "https://vidlink.pro/api/b/movie/{enc}?multiLang=0"
_API_TV = "https://vidlink.pro/api/b/tv/{enc}/{season}/{episode}?multiLang=0"
_REF = "https://vidlink.pro/"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
_TIMEOUT = 15

# Prefer higher quality first
_Q_ORDER = ("1080", "720", "480", "360", "240")


def _tmdb(content_id: str) -> Optional[str]:
    cid = (content_id or "").strip()
    if cid.isdigit():
        return cid
    return None


def _encode(tmdb: str) -> Optional[str]:
    r = requests.get(
        _ENC,
        params={"text": tmdb},
        headers={"User-Agent": _UA, "Accept": "application/json"},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    data = r.json() if r.text else {}
    return data.get("result") or data.get("text")


def _qualities(payload: Dict[str, Any]) -> List[Tuple[str, str]]:
    stream = (payload or {}).get("stream") or {}
    quals = stream.get("qualities") or {}
    out: List[Tuple[str, str]] = []
    for key in _Q_ORDER:
        entry = quals.get(key)
        if isinstance(entry, dict) and entry.get("url"):
            out.append((key, entry["url"]))
    # any other keys
    for key, entry in quals.items():
        if key in _Q_ORDER:
            continue
        if isinstance(entry, dict) and entry.get("url"):
            out.append((str(key), entry["url"]))
    return out


class VidLinkProvider:
    name = "vidlink"
    langs = ("en",)

    def resolve_movie(self, content_id: str) -> Dict[str, Any]:
        tmdb = _tmdb(content_id)
        if not tmdb:
            return empty_result(self.name, error="vidlink_needs_tmdb", ref_url=_REF)
        try:
            print(f"[VIDLINK] resolve movie tmdb={tmdb}")
            enc = _encode(tmdb)
            if not enc:
                return empty_result(self.name, error="vidlink_enc_fail", ref_url=_REF)
            r = requests.get(
                _API_MOVIE.format(enc=enc),
                headers={
                    "User-Agent": _UA,
                    "Accept": "application/json",
                    "Referer": _REF,
                    "Origin": "https://vidlink.pro",
                },
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            payload = r.json() if r.text else {}
            pairs = _qualities(payload)
            if not pairs:
                return empty_result(self.name, error="vidlink_no_streams", ref_url=_REF)
            urls = [u for _, u in pairs]
            print(f"[VIDLINK] movie tmdb={tmdb} qualities={[q for q,_ in pairs]}")
            return ok_result(
                self.name,
                urls[0],
                stream_type="mp4",
                candidates=urls,
                ref_url=_REF,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[VIDLINK] movie fail: {exc}")
            return empty_result(self.name, error="vidlink_error", ref_url=_REF)

    def resolve_tv(
        self, content_id: str, season: int = 1, episode: int = 1
    ) -> Dict[str, Any]:
        tmdb = _tmdb(content_id)
        if not tmdb:
            return empty_result(self.name, error="vidlink_needs_tmdb", ref_url=_REF)
        try:
            print(f"[VIDLINK] resolve tv tmdb={tmdb} S{season}E{episode}")
            enc = _encode(tmdb)
            if not enc:
                return empty_result(self.name, error="vidlink_enc_fail", ref_url=_REF)
            r = requests.get(
                _API_TV.format(enc=enc, season=season, episode=episode),
                headers={
                    "User-Agent": _UA,
                    "Accept": "application/json",
                    "Referer": _REF,
                    "Origin": "https://vidlink.pro",
                },
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            payload = r.json() if r.text else {}
            pairs = _qualities(payload)
            if not pairs:
                return empty_result(self.name, error="vidlink_no_streams", ref_url=_REF)
            urls = [u for _, u in pairs]
            print(f"[VIDLINK] tv tmdb={tmdb} qualities={[q for q,_ in pairs]}")
            return ok_result(
                self.name,
                urls[0],
                stream_type="mp4",
                candidates=urls,
                ref_url=_REF,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[VIDLINK] tv fail: {exc}")
            return empty_result(self.name, error="vidlink_error", ref_url=_REF)