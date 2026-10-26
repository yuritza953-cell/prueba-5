"""
Provider EN: 2embed.skin / 2embed.cc

Flujo:
  1) GET embed page por TMDB o IMDb
  2) Extrae iframes / data-src (vidsrc.*, hosters, etc.)
  3) Si es hoster conocido → hosters.resolve_hoster_url
  4) Si parece vidsrc family → reutiliza el resolver de vidsrc (m3u8 limpio)

No se envía el iframe al player.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests
import urllib3

from streams.base import empty_result, ok_result, normalize_result

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_BASES = (
    "https://www.2embed.skin",
    "https://www.2embed.cc",
)
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
_TIMEOUT = 18
_IFRAME_RE = re.compile(
    r"""(?:src|data-src)\s*=\s*["']([^"']+)["']""",
    re.I,
)
_VIDSRC_HINT = re.compile(
    r"vidsrc\.(?:sh|pm|net|xyz|in|buzz|me|to)|hnembed\.|stellarconductor",
    re.I,
)


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": _UA,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    return s


def _embed_paths(content_id: str, media: str, season: int, episode: int) -> List[str]:
    cid = (content_id or "").strip()
    paths: List[str] = []
    if media == "tv":
        for b in _BASES:
            paths.append(f"{b}/embedtv/{cid}&s={season}&e={episode}")
            paths.append(f"{b}/embed/tv?id={cid}&s={season}&e={episode}")
            if cid.startswith("tt"):
                paths.append(f"{b}/embedtv/{cid}&s={season}&e={episode}")
    else:
        for b in _BASES:
            paths.append(f"{b}/embed/{cid}")
            paths.append(f"{b}/embed/movie?id={cid}")
            if cid.startswith("tt"):
                paths.append(f"{b}/embed/{cid}")
            elif cid.isdigit():
                paths.append(f"{b}/embed/{cid}")
    # dedupe
    return list(dict.fromkeys(paths))


def _collect_frame_urls(html: str, page_url: str) -> List[str]:
    out: List[str] = []
    for u in _IFRAME_RE.findall(html or ""):
        u = u.strip()
        if not u or u.startswith("about:"):
            continue
        if u.startswith("//"):
            u = "https:" + u
        elif u.startswith("/"):
            u = urljoin(page_url, u)
        if u.startswith("http"):
            out.append(u)
    # también enlaces go('...')
    for u in re.findall(r"go\(\s*['\"](https?://[^'\"]+)['\"]", html or ""):
        out.append(u)
    return list(dict.fromkeys(out))


def _resolve_frames(frames: List[str]) -> List[str]:
    from streams.providers.hosters import resolve_hoster_url

    streams: List[str] = []
    seen = set()
    for fr in frames:
        if _VIDSRC_HINT.search(fr):
            # no scrapear el iframe vidsrc aquí; se delega fuera
            continue
        try:
            got = resolve_hoster_url(fr, referer=_BASES[0] + "/")
        except Exception as exc:
            print(f"[TWOEMBED] hoster fail {fr[:50]}: {exc}")
            continue
        for u in got or []:
            if u and u not in seen:
                seen.add(u)
                streams.append(u)
        if streams:
            break
    return streams


def _via_vidsrc(content_id: str, media: str, season: int, episode: int) -> Dict[str, Any]:
    from streams.legacy.vidsrc.stream_resolver import resolve_movie, resolve_tv

    if media == "tv":
        data = resolve_tv(content_id, season, episode)
    else:
        data = resolve_movie(content_id)
    return normalize_result("twoembed", data)


def _resolve(
    content_id: str,
    media: str = "movie",
    season: int = 1,
    episode: int = 1,
) -> Dict[str, Any]:
    cid = (content_id or "").strip()
    if not cid:
        return empty_result("twoembed", error="twoembed_needs_id")

    print(f"[TWOEMBED] resolve {media} id={cid}" + (f" S{season}E{episode}" if media == "tv" else ""))
    sess = _session()
    frames: List[str] = []
    last_page = _BASES[0]

    for path in _embed_paths(cid, media, season, episode):
        try:
            r = sess.get(path, timeout=_TIMEOUT, allow_redirects=True, verify=False)
        except Exception as exc:
            print(f"[TWOEMBED] page fail {path}: {exc}")
            continue
        if r.status_code >= 400 or not r.text:
            continue
        last_page = r.url
        found = _collect_frame_urls(r.text, r.url)
        if found:
            frames.extend(found)
            break

    frames = list(dict.fromkeys(frames))
    if frames:
        print(f"[TWOEMBED] frames={len(frames)} sample={frames[0][:70]}")
        streams = _resolve_frames(frames)
        if streams:
            print(f"[TWOEMBED] OK hoster streams={len(streams)}")
            st = "mp4" if streams[0].lower().split("?")[0].endswith(".mp4") else "hls"
            return ok_result(
                "twoembed",
                streams[0],
                stream_type=st,
                candidates=streams,
                ref_url=_BASES[0] + "/",
            )
        # si solo había vidsrc-like, caer al resolver vidsrc
        if any(_VIDSRC_HINT.search(f) for f in frames):
            print("[TWOEMBED] delegating to vidsrc family")
            data = _via_vidsrc(cid, media, season, episode)
            if data.get("stream_url"):
                data["provider"] = "twoembed"
                data["source"] = "twoembed"
                return data

    # último recurso: vidsrc directo (misma cobertura EN ampliada por mirrors)
    data = _via_vidsrc(cid, media, season, episode)
    if data.get("stream_url"):
        data["provider"] = "twoembed"
        data["source"] = "twoembed"
        return data

    return empty_result("twoembed", error=data.get("error") or "twoembed_no_stream", ref_url=last_page)


class TwoEmbedProvider:
    name = "twoembed"
    langs = ("en",)

    def resolve_movie(self, content_id: str) -> Dict[str, Any]:
        return _resolve(content_id, "movie")

    def resolve_tv(
        self, content_id: str, season: int = 1, episode: int = 1
    ) -> Dict[str, Any]:
        return _resolve(content_id, "tv", season, episode)

# alias por si el loader busca otro nombre
twoembed = TwoEmbedProvider