"""
Provider ES: moviedays.lat — embed engine por TMDB.

Flujo:
  1) GET https://moviedays.lat/ → extrae MD_EMBED_TS + MD_EMBED_SIG
  2) GET /api/embed.php?tmdb=&type=movie|tv|anime&_ts=&_sig=[&se=&ep=]
  3) Por cada server.url (vimeos, voe, etc.) → hosters.resolve_hoster_url → m3u8/mp4

Sin iframes al player: solo URLs de stream.
"""
from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional, Tuple

import requests
import urllib3

from streams.base import empty_result, ok_result

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_BASE = "https://moviedays.lat"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
_TIMEOUT = 20
_token_cache: Dict[str, Any] = {"ts": None, "sig": None, "at": 0.0}


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": _UA,
            "Accept": "application/json,text/html,*/*",
            "Accept-Language": "es-419,es;q=0.9,en;q=0.8",
            "Referer": _BASE + "/",
        }
    )
    return s


def _embed_tokens(sess: requests.Session) -> Tuple[Optional[str], Optional[str]]:
    now = time.time()
    if _token_cache["sig"] and now - float(_token_cache["at"] or 0) < 90:
        return _token_cache["ts"], _token_cache["sig"]
    try:
        r = sess.get(_BASE + "/", timeout=_TIMEOUT)
        html = r.text or ""
    except Exception as exc:
        print(f"[MOVIEDAYS] home fail: {exc}")
        return None, None
    m_ts = re.search(r"MD_EMBED_TS\s*=\s*(\d+)", html)
    m_sig = re.search(r'MD_EMBED_SIG\s*=\s*"([a-f0-9]+)"', html, re.I)
    if not m_ts or not m_sig:
        print("[MOVIEDAYS] no embed tokens in home")
        return None, None
    _token_cache["ts"] = m_ts.group(1)
    _token_cache["sig"] = m_sig.group(1)
    _token_cache["at"] = now
    return _token_cache["ts"], _token_cache["sig"]


def _resolve_servers(servers: List[Dict[str, Any]]) -> List[str]:
    from streams.providers.hosters import resolve_hoster_url

    out: List[str] = []
    seen = set()
    # Preferir latino / vimeos primero
    def score(s: Dict[str, Any]) -> tuple:
        lang = (s.get("lang") or s.get("audio") or "").lower()
        src = (s.get("source") or s.get("name") or "").lower()
        lat = 0 if "lat" in lang else 1
        vim = 0 if "vimeo" in src else 1
        return (lat, vim)

    for s in sorted(servers or [], key=score):
        url = (s.get("url") or s.get("embed") or "").strip()
        if not url.startswith("http"):
            continue
        try:
            streams = resolve_hoster_url(url, referer=_BASE + "/")
        except Exception as exc:
            print(f"[MOVIEDAYS] hoster fail {url[:60]}: {exc}")
            continue
        for u in streams or []:
            if not u or u in seen:
                continue
            low = u.lower()
            if "test-streams.mux.dev" in low or "example.com" in low or "placeholder" in low:
                print(f"[MOVIEDAYS] skip demo url {u[:70]}")
                continue
            seen.add(u)
            out.append(u)
        if out:
            break  # early-exit con el primer hoster válido
    return out


def _resolve(
    content_id: str,
    media: str = "movie",
    season: int = 1,
    episode: int = 1,
) -> Dict[str, Any]:
    tmdb = (content_id or "").strip()
    if not tmdb.isdigit():
        return empty_result("moviedays", error="moviedays_needs_tmdb", ref_url=_BASE + "/")

    kind = (media or "movie").lower()
    if kind in ("tv", "serie", "series"):
        api_type = "tv"
    elif kind == "anime":
        api_type = "anime"
    else:
        api_type = "movie"

    print(f"[MOVIEDAYS] resolve {api_type} tmdb={tmdb}" + (f" S{season}E{episode}" if api_type != "movie" else ""))
    sess = _session()
    ts, sig = _embed_tokens(sess)
    if not ts or not sig:
        return empty_result("moviedays", error="moviedays_no_tokens", ref_url=_BASE + "/")

    params: Dict[str, Any] = {
        "tmdb": tmdb,
        "type": api_type,
        "_ts": ts,
        "_sig": sig,
    }
    if api_type in ("tv", "anime"):
        params["se"] = int(season)
        params["ep"] = int(episode)

    try:
        r = sess.get(f"{_BASE}/api/embed.php", params=params, timeout=_TIMEOUT)
        data = r.json()
    except Exception as exc:
        print(f"[MOVIEDAYS] embed api fail: {exc}")
        return empty_result("moviedays", error="moviedays_api_error", ref_url=_BASE + "/")

    if not data.get("success"):
        err = data.get("error") or "moviedays_no_success"
        print(f"[MOVIEDAYS] fail: {err}")
        return empty_result("moviedays", error=str(err)[:120], ref_url=_BASE + "/")

    servers = data.get("servers") or []
    if not servers:
        return empty_result("moviedays", error="moviedays_no_servers", ref_url=_BASE + "/")

    streams = _resolve_servers(servers)
    if not streams:
        # devolver al menos el embed crudo no sirve al player; reportar fallo limpio
        print("[MOVIEDAYS] servers sin m3u8/mp4 resoluble")
        return empty_result("moviedays", error="moviedays_no_stream", ref_url=_BASE + "/")

    print(f"[MOVIEDAYS] OK streams={len(streams)} host={streams[0].split('/')[2]}")
    st = "mp4" if streams[0].lower().split("?")[0].endswith(".mp4") else "hls"
    return ok_result(
        "moviedays",
        streams[0],
        stream_type=st,
        candidates=streams,
        ref_url=_BASE + "/",
    )


class MovieDaysProvider:
    name = "moviedays"
    langs = ("es",)

    def resolve_movie(self, content_id: str) -> Dict[str, Any]:
        return _resolve(content_id, "movie")

    def resolve_tv(
        self, content_id: str, season: int = 1, episode: int = 1
    ) -> Dict[str, Any]:
        data = _resolve(content_id, "tv", season, episode)
        if data.get("stream_url"):
            return data
        anime = _resolve(content_id, "anime", season, episode)
        if anime.get("stream_url"):
            return anime
        return data