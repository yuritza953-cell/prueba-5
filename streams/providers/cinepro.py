"""
Provider opcional: CinePro Core (https://github.com/cinepro-org/core).

No embebe el código de CinePro. Llama a una instancia que tú levantes
(Docker / Node) vía su API OMSS:

  GET {CINEPRO_BASE_URL}/v1/movies/{tmdb}
  GET {CINEPRO_BASE_URL}/v1/tv/{tmdb}?season=&episode=

Activar:
  CINEPRO_BASE_URL=http://127.0.0.1:3000
  (y opcionalmente CINEPRO_IN_CHAIN=1 para meterlo en la cadena es/en)

Respuestas típicas traen sources[].url (a veces ya proxied por CinePro).
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests
import urllib3

from streams.base import empty_result, ok_result

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_TIMEOUT = int(os.environ.get("CINEPRO_TIMEOUT", "25"))


def _base() -> str:
    return (os.environ.get("CINEPRO_BASE_URL") or "").rstrip("/")


def _headers() -> Dict[str, str]:
    h = {"Accept": "application/json", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"}
    key = (os.environ.get("CINEPRO_API_KEY") or "").strip()
    if key:
        h["Authorization"] = f"Bearer {key}"
    return h


def _collect_urls(payload: Dict[str, Any], base: str) -> List[str]:
    out: List[str] = []
    for src in payload.get("sources") or []:
        if not isinstance(src, dict):
            continue
        u = src.get("url") or src.get("stream") or src.get("file")
        if not u:
            continue
        u = str(u).strip()
        if u.startswith("/"):
            u = urljoin(base + "/", u.lstrip("/"))
        if u.startswith("http"):
            out.append(u)
    return out


def _resolve(path: str) -> Dict[str, Any]:
    base = _base()
    if not base:
        return empty_result("cinepro", error="cinepro_not_configured")

    url = f"{base}{path}"
    try:
        r = requests.get(url, headers=_headers(), timeout=_TIMEOUT)
        if r.status_code == 404:
            return empty_result("cinepro", error="cinepro_not_found", ref_url=url)
        r.raise_for_status()
        data = r.json() if r.text else {}
    except Exception as exc:
        print(f"[CINEPRO] fail {url}: {exc}")
        return empty_result("cinepro", error="cinepro_error", ref_url=url)

    urls = _collect_urls(data if isinstance(data, dict) else {}, base)
    if not urls:
        return empty_result("cinepro", error="cinepro_no_sources", ref_url=url)

    first = urls[0]
    st = "mp4" if ".mp4" in first.lower().split("?")[0] else "hls"
    print(f"[CINEPRO] OK sources={len(urls)} type={st}")
    return ok_result(
        "cinepro",
        first,
        stream_type=st,
        candidates=urls,
        ref_url=base,
    )


class CineProProvider:
    name = "cinepro"
    langs = ("es", "en")

    def resolve_movie(self, content_id: str) -> Dict[str, Any]:
        cid = str(content_id).strip()
        if not cid.isdigit():
            return empty_result(self.name, error="cinepro_needs_tmdb")
        return _resolve(f"/v1/movies/{cid}")

    def resolve_tv(
        self, content_id: str, season: int = 1, episode: int = 1
    ) -> Dict[str, Any]:
        cid = str(content_id).strip()
        if not cid.isdigit():
            return empty_result(self.name, error="cinepro_needs_tmdb")
        return _resolve(f"/v1/tv/{cid}?season={int(season)}&episode={int(episode)}")
