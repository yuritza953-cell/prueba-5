"""
Provider ES: lamovie.org

Flujo (inspirado en Nuvio Providers Latino):
  1) TMDB → título / año / géneros
  2) Probar slugs /peliculas|series|animes/{slug}-{year}/
  3) shortlink ?p=ID → /wp-api/v1/player?postId=
  4) embeds[] → hosters.resolve_hoster_url → m3u8/mp4
"""
from __future__ import annotations

import os
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

import requests
import urllib3

from streams.base import empty_result, ok_result

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_BASE = "https://lamovie.org"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
_TIMEOUT = 18
_ANIME_COUNTRIES = {"JP", "CN", "KR"}
_GENRE_ANIMATION = 16


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": _UA,
            "Accept": "text/html,application/json,*/*",
            "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
        }
    )
    return s


def _slug(title: str, year: str = "") -> str:
    t = unicodedata.normalize("NFD", title or "")
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = t.lower()
    t = re.sub(r"[^a-z0-9\s-]", " ", t)
    t = re.sub(r"\s+", "-", t.strip())
    t = re.sub(r"-+", "-", t).strip("-")
    if year and year.isdigit():
        return f"{t}-{year}"
    return t


def _tmdb_info(sess: requests.Session, tmdb: str, media: str) -> Optional[Dict[str, Any]]:
    key = (os.environ.get("TMDB_API_KEY") or "").strip()
    if not key or key.startswith("eyJ"):
        # sin key v3 no consultamos TMDB aquí; el caller puede fallar
        # (Kinora suele tener TMDB_API_KEY en .env)
        if not key:
            return None
    media_type = "tv" if media in ("tv", "anime") else "movie"
    params: Dict[str, str] = {"language": "es-MX"}
    headers = {"Accept": "application/json", "User-Agent": _UA}
    if key.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {key}"
    else:
        params["api_key"] = key
    try:
        r = sess.get(
            f"https://api.themoviedb.org/3/{media_type}/{tmdb}",
            params=params,
            headers=headers,
            timeout=_TIMEOUT,
        )
        if r.status_code >= 400:
            return None
        data = r.json()
    except Exception:
        return None
    title = data.get("title") or data.get("name") or ""
    original = data.get("original_title") or data.get("original_name") or title
    year = (data.get("release_date") or data.get("first_air_date") or "")[:4]
    genres = [g.get("id") for g in (data.get("genres") or []) if g.get("id")]
    origins = list(data.get("origin_country") or [])
    if not origins:
        origins = [
            c.get("iso_3166_1")
            for c in (data.get("production_countries") or [])
            if c.get("iso_3166_1")
        ]
    return {
        "title": title,
        "original": original,
        "year": year,
        "genres": genres,
        "origins": origins,
    }


def _categories(media: str, genres: List[int], origins: List[str]) -> List[str]:
    if media == "movie":
        return ["peliculas"]
    is_anim = _GENRE_ANIMATION in (genres or [])
    if not is_anim:
        return ["series"]
    if any(c in _ANIME_COUNTRIES for c in (origins or [])):
        return ["animes"]
    return ["animes", "series"]


def _post_id_from_slug(sess: requests.Session, category: str, slug: str) -> Optional[str]:
    url = f"{_BASE}/{category}/{slug}/"
    try:
        r = sess.get(url, timeout=_TIMEOUT, allow_redirects=True)
    except Exception:
        return None
    if r.status_code >= 400:
        return None
    m = re.search(
        r"rel=['\"]shortlink['\"]\s+href=['\"][^'\"]*\?p=(\d+)['\"]",
        r.text or "",
    )
    return m.group(1) if m else None


def _find_post(
    sess: requests.Session, info: Dict[str, Any], media: str
) -> Optional[str]:
    cats = _categories(media, info.get("genres") or [], info.get("origins") or [])
    slugs = []
    for title in (info.get("title"), info.get("original")):
        if not title:
            continue
        slugs.append(_slug(title, info.get("year") or ""))
        slugs.append(_slug(title, ""))  # sin año
    tried = set()
    for slug in slugs:
        if not slug or slug in tried:
            continue
        tried.add(slug)
        for cat in cats:
            pid = _post_id_from_slug(sess, cat, slug)
            if pid:
                print(f"[LAMOVIE] slug /{cat}/{slug} → id={pid}")
                return pid
    return None


def _episode_id(
    sess: requests.Session, series_id: str, season: int, episode: int
) -> Optional[str]:
    url = (
        f"{_BASE}/wp-api/v1/single/episodes/list"
        f"?_id={series_id}&season={season}&page=1&postsPerPage=80"
    )
    try:
        r = sess.get(url, timeout=_TIMEOUT, headers={"Accept": "application/json"})
        data = r.json()
    except Exception:
        return None
    posts = (data.get("data") or {}).get("posts") or []
    for ep in posts:
        if int(ep.get("season_number") or 0) == int(season) and int(
            ep.get("episode_number") or 0
        ) == int(episode):
            return str(ep.get("_id") or "") or None
    return None


def _player_embeds(sess: requests.Session, post_id: str) -> List[str]:
    try:
        r = sess.get(
            f"{_BASE}/wp-api/v1/player",
            params={"postId": post_id, "demo": 0},
            timeout=_TIMEOUT,
            headers={"Accept": "application/json"},
        )
        data = r.json()
    except Exception as exc:
        print(f"[LAMOVIE] player fail: {exc}")
        return []
    embeds = (data.get("data") or {}).get("embeds") or []
    urls = []
    for e in embeds:
        u = (e.get("url") or "").strip()
        if u.startswith("http") and not u.startswith("magnet:"):
            urls.append(u)
    return urls


def _resolve_embeds(urls: List[str]) -> List[str]:
    from streams.providers.hosters import resolve_hoster_url

    out: List[str] = []
    seen = set()
    for url in urls:
        try:
            streams = resolve_hoster_url(url, referer=_BASE + "/")
        except Exception as exc:
            print(f"[LAMOVIE] hoster fail {url[:50]}: {exc}")
            continue
        for u in streams or []:
            if u and u not in seen:
                seen.add(u)
                out.append(u)
        if out:
            break
    return out


def _resolve(
    content_id: str,
    media: str = "movie",
    season: int = 1,
    episode: int = 1,
) -> Dict[str, Any]:
    tmdb = (content_id or "").strip()
    if not tmdb.isdigit():
        return empty_result("lamovie", error="lamovie_needs_tmdb", ref_url=_BASE + "/")

    print(f"[LAMOVIE] resolve {media} tmdb={tmdb}" + (f" S{season}E{episode}" if media != "movie" else ""))
    sess = _session()
    info = _tmdb_info(sess, tmdb, media)
    if not info:
        return empty_result("lamovie", error="lamovie_tmdb_fail", ref_url=_BASE + "/")

    post_id = _find_post(sess, info, media)
    if not post_id:
        print("[LAMOVIE] no post by slug")
        return empty_result("lamovie", error="lamovie_not_found", ref_url=_BASE + "/")

    if media in ("tv", "anime"):
        ep_id = _episode_id(sess, post_id, season, episode)
        if not ep_id:
            return empty_result("lamovie", error="lamovie_no_episode", ref_url=_BASE + "/")
        post_id = ep_id

    embeds = _player_embeds(sess, post_id)
    if not embeds:
        return empty_result("lamovie", error="lamovie_no_embeds", ref_url=_BASE + "/")

    streams = _resolve_embeds(embeds)
    if not streams:
        return empty_result("lamovie", error="lamovie_no_stream", ref_url=_BASE + "/")

    print(f"[LAMOVIE] OK streams={len(streams)} host={streams[0].split('/')[2]}")
    st = "mp4" if streams[0].lower().split("?")[0].endswith(".mp4") else "hls"
    return ok_result(
        "lamovie",
        streams[0],
        stream_type=st,
        candidates=streams,
        ref_url=_BASE + "/",
    )


class LaMovieProvider:
    name = "lamovie"
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