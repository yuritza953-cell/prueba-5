"""
Provider EN: VidFast — probe/decrypt vía enc-dec.app (sin reimplementar crypto).

Flujo (sample EncDecEndpoints):
  1) GET embed page → token
  2) enc-vidfast stage=1 → POST stage1
  3) enc-vidfast stage=2 → servers + stream + csrf
  4) POST servers → dec-vidfast
  5) POST stream/{data} → dec-vidfast → {url: m3u8}
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests
import urllib3

from streams.base import empty_result, ok_result

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_BASE = "https://vidfast.vc"
_API = "https://enc-dec.app/api"
_TIMEOUT = 18


def _ua() -> str:
    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0.0.0 Safari/537.36"
    )


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
    if is_tv:
        page = f"{_BASE}/tv/{tmdb}/{int(season)}/{int(episode)}/"
        label = f"tv {tmdb} S{season}E{episode}"
    else:
        page = f"{_BASE}/movie/{tmdb}/"
        label = f"movie {tmdb}"
    print(f"[VIDFAST] resolve {label}")

    sess = requests.Session()
    try:
        html = sess.get(page, headers={"User-Agent": _ua()}, timeout=_TIMEOUT, verify=False).text
    except Exception as exc:
        return empty_result("vidfast", error=f"vidfast_page:{exc}", ref_url=_BASE + "/")

    m = re.search(r'\\"(?:en|token)\\":\\"(.*?)\\"', html)
    if not m:
        m = re.search(r'\\?"(?:en|token)\\?":\\?"([^"\\]+)', html)
    if not m:
        return empty_result("vidfast", error="vidfast_no_token", ref_url=page)
    en_token = m.group(1)

    headers = {
        "User-Agent": _ua(),
        "Referer": f"{_BASE}/",
        "Origin": _BASE,
        "X-Requested-With": "XMLHttpRequest",
    }

    try:
        r1 = sess.get(
            f"{_API}/enc-vidfast?text={quote(en_token)}&stage=1",
            headers={"User-Agent": _ua()},
            timeout=_TIMEOUT,
        ).json()
        if r1.get("status") != 200:
            return empty_result("vidfast", error="vidfast_enc1", ref_url=page)
        p1 = r1["result"]
        headers["X-CSRF-Token"] = p1.get("token") or ""
        stage1_body = sess.post(p1["stage1"], headers=headers, timeout=_TIMEOUT, verify=False).text
        if not stage1_body:
            return empty_result("vidfast", error="vidfast_stage1_empty", ref_url=page)

        r2 = sess.get(
            f"{_API}/enc-vidfast?text={quote(stage1_body)}&stage=2",
            headers={"User-Agent": _ua()},
            timeout=_TIMEOUT,
        ).json()
        if r2.get("status") != 200:
            return empty_result("vidfast", error="vidfast_enc2", ref_url=page)
        p2 = r2["result"]
        headers["X-CSRF-Token"] = p2.get("token") or ""
        servers_url = p2["servers"]
        stream_base = p2["stream"]

        servers_enc = sess.post(servers_url, headers=headers, timeout=_TIMEOUT, verify=False).text
        if not servers_enc:
            return empty_result("vidfast", error="vidfast_servers_empty", ref_url=page)

        dec = sess.post(
            f"{_API}/dec-vidfast",
            json={"text": servers_enc},
            headers={"User-Agent": _ua()},
            timeout=_TIMEOUT,
        ).json()
        if dec.get("status") != 200:
            return empty_result("vidfast", error="vidfast_dec_servers", ref_url=page)

        servers: List[dict] = dec.get("result") or []
        if not isinstance(servers, list) or not servers:
            return empty_result("vidfast", error="vidfast_no_servers", ref_url=page)

        candidates: List[str] = []
        primary = None
        for srv in servers[:4]:
            data = (srv or {}).get("data")
            if not data:
                continue
            stream_url = f"{stream_base.rstrip('/')}/{data}"
            try:
                se = sess.post(stream_url, headers=headers, timeout=_TIMEOUT, verify=False).text
                if not se:
                    continue
                d2 = sess.post(
                    f"{_API}/dec-vidfast",
                    json={"text": se},
                    headers={"User-Agent": _ua()},
                    timeout=_TIMEOUT,
                ).json()
                if d2.get("status") != 200:
                    continue
                payload = d2.get("result") or {}
                u = payload.get("url") if isinstance(payload, dict) else None
                if isinstance(u, str) and u.startswith("http"):
                    candidates.append(u)
                    if primary is None:
                        primary = u
                        print(f"[VIDFAST] OK server={(srv or {}).get('name')}")
            except Exception as exc:
                print(f"[VIDFAST] server fail: {exc}")

        if not primary:
            return empty_result("vidfast", error="vidfast_no_streams", ref_url=page)

        return ok_result(
            "vidfast",
            primary,
            stream_type="hls",
            candidates=list(dict.fromkeys(candidates)),
            ref_url=_BASE + "/",
        )
    except Exception as exc:
        print(f"[VIDFAST] error: {exc}")
        return empty_result("vidfast", error="vidfast_exception", ref_url=page)


class VidFastProvider:
    name = "vidfast"
    langs = ("en",)

    def resolve_movie(self, content_id: str) -> Dict[str, Any]:
        tmdb = _tmdb(content_id)
        if not tmdb:
            return empty_result(self.name, error="vidfast_needs_tmdb", ref_url=_BASE + "/")
        return _resolve(tmdb)

    def resolve_tv(
        self, content_id: str, season: int = 1, episode: int = 1
    ) -> Dict[str, Any]:
        tmdb = _tmdb(content_id)
        if not tmdb:
            return empty_result(self.name, error="vidfast_needs_tmdb", ref_url=_BASE + "/")
        return _resolve(tmdb, season=season, episode=episode)