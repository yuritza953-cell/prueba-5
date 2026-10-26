"""
PlayLatinSRC stream resolver (español / latino).

Flujo:
  1. GET /custom/movie|tv/... → data-resolve-token
  2. POST /api/resolve
  3. Prefer latino + mixdrop; scrapear hosters
  4. ref_url = dominio del hoster (mxdrop.to), NUNCA playlatinsrc.co
     (mxcontent.net responde 403 con Referer de playlatinsrc)

VidSrc NO se usa aquí.
"""
from __future__ import annotations

import os
import random
import re
import string
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, urljoin, urlparse

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from .constants import BASE_URL, EMBED_MOVIE, EMBED_TV, HTTP_TIMEOUT, RESOLVE_API

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
_TIMEOUT = (10, max(HTTP_TIMEOUT, 30))

_MIXDROP_HOSTS = (
    "mixdrop",
    "mxdrop",
    "mixdroop",
    "mdy48tn97",
    "mdbekjwqa",
    "mixdropjmk",
)


def _parse_proxy_list(raw: str) -> List[str]:
    out: List[str] = []
    if not raw:
        return out
    for line in raw.replace(";", ",").split(","):
        line = line.strip()
        if not line:
            continue
        if "://" in line or "@" in line:
            if not line.startswith("http"):
                line = "http://" + line
            out.append(line)
            continue
        parts = line.split(":")
        if len(parts) >= 4:
            host, port, user, passwd = parts[0], parts[1], parts[2], ":".join(parts[3:])
            out.append(
                "http://%s:%s@%s:%s"
                % (quote(user, safe=""), quote(passwd, safe=""), host, port)
            )
        elif len(parts) == 2:
            out.append("http://%s:%s" % (parts[0], parts[1]))
    return out


_PROXY_LIST = _parse_proxy_list(os.environ.get("PROXY_LIST") or "")
_PROXY_IDX = 0
_DIRECT_FIRST = os.environ.get("DIRECT_FIRST", "1").lower() not in ("0", "false", "no")


def _next_proxy() -> Optional[dict]:
    global _PROXY_IDX
    if not _PROXY_LIST:
        return None
    u = _PROXY_LIST[_PROXY_IDX % len(_PROXY_LIST)]
    _PROXY_IDX += 1
    return {"http": u, "https": u}


def _egress_attempts() -> List[Optional[dict]]:
    attempts: List[Optional[dict]] = []
    if _DIRECT_FIRST or not _PROXY_LIST:
        attempts.append(None)
    if _PROXY_LIST:
        for _ in range(min(3, len(_PROXY_LIST))):
            attempts.append(_next_proxy())
    return attempts or [None]


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": _UA,
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.5",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )
    return s


def _unique(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for x in items:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _is_mixdrop(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(h in host for h in _MIXDROP_HOSTS)


def _host_origin(url: str) -> str:
    p = urlparse(url)
    if not p.scheme or not p.netloc:
        return "https://mxdrop.to/"
    return f"{p.scheme}://{p.netloc}/"


def _unpack_packer(html: str) -> Optional[str]:
    m = re.search(r"}\('(.+)',(\d+),(\d+),'(.+)'\.split\('\|'\)", html, re.S)
    if not m:
        return None
    p, a, c, k = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4).split("|")
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def base_n(n: int) -> str:
        if n == 0:
            return alphabet[0]
        out = ""
        while n:
            out = alphabet[n % a] + out
            n //= a
        return out

    table = {}
    for i in range(c):
        key = base_n(i)
        table[key] = k[i] if i < len(k) and k[i] else key

    def repl(mo: re.Match) -> str:
        w = mo.group(0)
        return table.get(w, w)

    try:
        return re.sub(r"\b\w+\b", repl, p)
    except Exception:
        return None


def _extract_mixdrop_mp4(html: str) -> Optional[str]:
    low = (html or "").lower()
    if "we are sorry" in low or "can't find the video" in low or "cant find the video" in low:
        return None
    decoded = _unpack_packer(html) or ""
    blob = decoded + "\n" + html
    m = re.search(r'MDCore\.wurl\s*=\s*["\']([^"\']+)["\']', blob)
    if not m:
        m = re.search(r'wurl\s*[:=]\s*["\']([^"\']+\.mp4[^"\']*)["\']', blob, re.I)
    if not m:
        m = re.search(r'(//[a-z0-9.-]*mxcontent\.net/[^"\']+\.mp4[^"\']*)', blob, re.I)
    if not m:
        return None
    url = m.group(1).strip()
    if url.startswith("//"):
        url = "https:" + url
    if url.startswith("http") and ".mp4" in url.lower():
        return url
    return None


def _extract_dood(html: str, base_url: str, sess: requests.Session, proxies) -> Optional[str]:
    low = (html or "").lower()
    if "just a moment" in low or "cf-chl" in low or "challenge-platform" in low:
        return None
    m = re.search(r"(/pass_md5/[a-zA-Z0-9/_\-]+)", html)
    if not m:
        return None
    path = m.group(1)
    token_m = re.search(
        r"token=([a-zA-Z0-9]+)|makePlay\([^,]+,\s*['\"]([a-zA-Z0-9]+)", html
    )
    token = ""
    if token_m:
        token = token_m.group(1) or token_m.group(2) or ""
    pass_url = urljoin(base_url, path)
    try:
        r = sess.get(
            pass_url,
            headers={"Referer": base_url, "Accept": "*/*"},
            timeout=_TIMEOUT,
            proxies=proxies,
            verify=False,
        )
        if r.status_code >= 400 or not r.text:
            return None
        base_media = r.text.strip().split("\n")[0].strip()
        if not base_media.startswith("http"):
            return None
        rnd = "".join(random.choices(string.ascii_letters + string.digits, k=10))
        if token:
            return f"{base_media}{rnd}?token={token}&expiry={int(time.time() * 1000)}"
        return base_media + rnd
    except Exception as exc:
        print(f"[PLAYLATIN] dood pass_md5 fail: {exc}")
        return None


def _get_html(
    sess: requests.Session, url: str, referer: str, proxies
) -> Tuple[Optional[str], str, int]:
    try:
        r = sess.get(
            url,
            headers={
                "Referer": referer,
                "Origin": BASE_URL,
                "Accept": "text/html,*/*",
            },
            timeout=_TIMEOUT,
            allow_redirects=True,
            verify=False,
            proxies=proxies,
        )
        return (r.text or None), (r.url or url), r.status_code
    except Exception as exc:
        print(f"[PLAYLATIN] get fail {urlparse(url).hostname}: {exc}")
        return None, url, 0


def _scrape_hoster(
    sess: requests.Session, embed_url: str, referer: str
) -> Optional[Tuple[str, str, str]]:
    """(media_url, stream_type, cdn_referer) — cdn_referer NUNCA es playlatinsrc."""
    last_status = 0
    for proxies in _egress_attempts():
        html, final, status = _get_html(sess, embed_url, referer, proxies)
        last_status = status
        if not html:
            continue
        low = html.lower()
        if "just a moment" in low or "cf-chl" in low:
            print(
                f"[PLAYLATIN] hoster CF challenge {urlparse(final).hostname} "
                f"via={'proxy' if proxies else 'direct'}"
            )
            continue

        if _is_mixdrop(final) or _is_mixdrop(embed_url):
            if "we are sorry" in low or "can't find the video" in low:
                print(f"[PLAYLATIN] mixdrop dead {urlparse(final).hostname}")
                return None
            mp4 = _extract_mixdrop_mp4(html)
            if mp4:
                cdn_ref = _host_origin(final if _is_mixdrop(final) else embed_url)
                print(f"[PLAYLATIN] mixdrop mp4 {mp4[:90]} ref={cdn_ref}")
                return mp4, "mp4", cdn_ref
            print(f"[PLAYLATIN] mixdrop sin wurl host={urlparse(final).hostname}")

        if "dood" in (urlparse(final).hostname or "") or "dood" in embed_url:
            dood = _extract_dood(html, final, sess, proxies)
            if dood:
                cdn_ref = _host_origin(final)
                print(f"[PLAYLATIN] dood {dood[:90]}")
                return dood, "mp4", cdn_ref

        for pat, kind in (
            (r'https?://[^"\'\s<>]+?\.m3u8[^"\'\s<>]*', "hls"),
            (r'https?://[^"\'\s<>]+?\.mp4[^"\'\s<>]*', "mp4"),
        ):
            for m in re.finditer(pat, html, re.I):
                u = m.group(0).replace("\\/", "/")
                if any(
                    x in u.lower()
                    for x in ("recaptcha", "google", "facebook", "tiktok", "turnstile")
                ):
                    continue
                cdn_ref = _host_origin(final)
                print(f"[PLAYLATIN] html {kind} {u[:90]}")
                return u, kind, cdn_ref

    print(f"[PLAYLATIN] hoster fail {urlparse(embed_url).hostname} last_status={last_status}")
    return None


def _fetch_token_page(
    sess: requests.Session, content_type: str, content_id: str, season: int, episode: int
) -> Tuple[Optional[str], str]:
    if content_type == "tv":
        url = EMBED_TV.format(content_id=content_id, season=season, episode=episode)
    else:
        url = EMBED_MOVIE.format(content_id=content_id)
    try:
        r = sess.get(
            url,
            headers={"Referer": BASE_URL + "/", "Accept": "text/html"},
            timeout=_TIMEOUT,
            allow_redirects=True,
        )
        r.raise_for_status()
        html = r.text or ""
    except Exception as exc:
        print(f"[PLAYLATIN] embed fail: {exc}")
        return None, url
    m = re.search(r'data-resolve-token="([^"]+)"', html)
    if not m:
        print("[PLAYLATIN] embed sin token")
        return None, url
    return m.group(1), url


def _api_resolve(
    sess: requests.Session,
    token: str,
    content_type: str,
    content_id: str,
    season: int,
    episode: int,
    embed_url: str,
) -> List[Dict[str, Any]]:
    body = {
        "type": "tv" if content_type == "tv" else "movie",
        "id": str(content_id),
        "season": str(season if content_type == "tv" else 1),
        "episode": str(episode if content_type == "tv" else 1),
        "mode": "custom",
        "token": token,
    }
    try:
        r = sess.post(
            RESOLVE_API,
            json=body,
            headers={
                "Content-Type": "application/json",
                "Referer": embed_url,
                "Origin": BASE_URL,
                "Accept": "application/json",
            },
            timeout=_TIMEOUT,
        )
        data = r.json()
    except Exception as exc:
        print(f"[PLAYLATIN] api_resolve error: {exc}")
        return []
    if not isinstance(data, dict) or data.get("ok") is False:
        print(f"[PLAYLATIN] api_resolve fail: {data}")
        return []
    sources = data.get("sources") or []
    return sources if isinstance(sources, list) else []


def _pick_sources(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def score(s: Dict[str, Any]) -> Tuple[int, int, int]:
        ver = (s.get("version") or "").lower()
        # "" (sin version) suele ser el único host de series → tratarlo como latino
        ver_rank = 0 if ver in ("latino", "") else (1 if ver == "castellano" else 9)
        url = str(s.get("url") or "")
        mix = 0 if _is_mixdrop(url) else 1
        rank = int(s.get("rank") or 99)
        return (ver_rank, mix, rank)

    filtered = []
    for s in sources:
        if not isinstance(s, dict):
            continue
        if not str(s.get("url") or "").startswith("http"):
            continue
        ver = (s.get("version") or "").lower()
        # latino/castellano, o sin version (algunas series solo traen un host)
        if ver in ("latino", "castellano", ""):
            filtered.append(s)
    if not filtered:
        # último recurso: cualquier source http (mejor que nada)
        filtered = [
            s for s in sources
            if isinstance(s, dict) and str(s.get("url") or "").startswith("http")
        ]
    filtered.sort(key=score)
    return filtered


def _resolve_chain(
    content_type: str, content_id: str, season: int = 1, episode: int = 1
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "stream_url": None,
        "stream_type": None,
        "candidates": [],
        "providers": [],
        "embed_url": None,
        "ref_url": BASE_URL + "/",
        "error": None,
        "source": "playlatinsrc",
    }
    sess = _session()
    token, embed_url = _fetch_token_page(sess, content_type, content_id, season, episode)
    result["embed_url"] = embed_url
    if not token:
        result["error"] = "playlatin_no_token"
        return result

    sources = _api_resolve(sess, token, content_type, content_id, season, episode, embed_url)
    if not sources:
        result["error"] = "playlatin_no_sources"
        return result

    picked = _pick_sources(sources)
    result["providers"] = [str(s.get("url")) for s in picked[:8]]
    print(f"[PLAYLATIN] {len(picked)} sources (prefer latino/mixdrop) proxies={len(_PROXY_LIST)}")

    if not picked:
        result["error"] = "playlatin_no_sources"
        return result

    working: List[str] = []
    stream_type = "mp4"
    cdn_ref = "https://mxdrop.to/"
    for src in picked:
        embed = str(src.get("url"))
        got = _scrape_hoster(sess, embed, embed_url)
        if not got:
            continue
        media, kind, cdn_ref = got
        working.append(media)
        stream_type = kind
        break

    result["candidates"] = _unique(working)[:3]
    if working:
        result["stream_url"] = working[0]
        result["stream_type"] = stream_type
        result["ref_url"] = cdn_ref  # mxdrop.to — no playlatinsrc
    else:
        result["error"] = "playlatin_no_media"
    return result


def resolve_movie(content_id: str) -> Dict[str, Any]:
    print(f"[PLAYLATIN] resolve movie {content_id}")
    t0 = time.time()
    data = _resolve_chain("movie", content_id)
    data["source"] = "playlatinsrc"
    print(
        f"[PLAYLATIN] done movie in {time.time()-t0:.1f}s "
        f"url={(data.get('stream_url') or '')[:80]} ref={data.get('ref_url')} "
        f"err={data.get('error')}"
    )
    return data


def resolve_tv(content_id: str, season: int = 1, episode: int = 1) -> Dict[str, Any]:
    print(f"[PLAYLATIN] resolve tv {content_id} S{season}E{episode}")
    t0 = time.time()
    data = _resolve_chain("tv", content_id, season, episode)
    data["source"] = "playlatinsrc"
    print(
        f"[PLAYLATIN] done tv in {time.time()-t0:.1f}s "
        f"url={(data.get('stream_url') or '')[:80]} ref={data.get('ref_url')} "
        f"err={data.get('error')}"
    )
    return data