"""
Provider ES: sitios WordPress estilo DooPlay / SoloLatino.

Estrategia:
  1) Buscar título (TMDB es-MX o query) en ?s=
  2) Abrir ficha → opciones dooplay_player_option
  3) POST admin-ajax.php action=doo_player_ajax → embed_url
  4) Pasar embed por hosters (StreamWish/VOE/etc.) si están disponibles

Mirrors rotan; se prueban varios dominios.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, urljoin, urlparse

import requests
import urllib3

from streams.base import empty_result, ok_result

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_MIRRORS = [
    "https://sololatino.net",
    "https://www.sololatino.net",
    "https://ww1.sololatino.net",
    "https://sololatino.bio",
    "https://www.seriesmetro.net",
    "https://seriesmetro.net",
    "https://tioplus.app",
]
_TIMEOUT = 6


def _headers(ref: str = "") -> Dict[str, str]:
    h = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-419,es;q=0.9,en;q=0.5",
    }
    if ref:
        h["Referer"] = ref
    return h


def _slugify(title: str) -> str:
    s = (title or "").lower().strip()
    s = re.sub(r"[áàäâ]", "a", s)
    s = re.sub(r"[éèëê]", "e", s)
    s = re.sub(r"[íìïî]", "i", s)
    s = re.sub(r"[óòöô]", "o", s)
    s = re.sub(r"[úùüû]", "u", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def _tmdb_title(tmdb_id: str, is_tv: bool) -> Optional[str]:
    """Título en español si hay TMDB_API_KEY (soporta v3 api_key o v4 Bearer); si no, None."""
    import os

    key = (os.environ.get("TMDB_API_KEY") or os.environ.get("TMDB_KEY") or "").strip()
    if not tmdb_id.isdigit():
        return None
    if not key:
        print("[SOLOLATINO] TMDB_API_KEY ausente — no se puede resolver título", flush=True)
        return None
    kind = "tv" if is_tv else "movie"
    headers = {"Accept": "application/json"}
    if key.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {key}"
        url = f"https://api.themoviedb.org/3/{kind}/{tmdb_id}?language=es-MX"
    else:
        url = f"https://api.themoviedb.org/3/{kind}/{tmdb_id}?api_key={key}&language=es-MX"
    try:
        r = requests.get(url, headers=headers, timeout=10)
        j = r.json()
        return j.get("title") or j.get("name") or j.get("original_title") or j.get("original_name")
    except Exception:
        return None


def _find_post_url(sess: requests.Session, base: str, query: str) -> Optional[str]:
    search = f"{base}/?s={quote(query)}"
    try:
        r = sess.get(search, headers=_headers(base + "/"), timeout=_TIMEOUT, verify=False)
        if r.status_code != 200:
            return None
        # enlaces a pelicula/series
        for pat in [
            r'href=["\']([^"\']+/(?:pelicula|movies?|series?|episodio)[^"\']+)["\']',
            r'href=["\']([^"\']+/[^"\']+)["\'][^>]*>\s*' + re.escape(query[:20]),
        ]:
            for m in re.finditer(pat, r.text, re.I):
                href = m.group(1)
                if "wp-" in href or "feed" in href:
                    continue
                return urljoin(base + "/", href)
        # slug directo
        slug = _slugify(query)
        for path in (f"/pelicula/{slug}/", f"/movies/{slug}/", f"/serie/{slug}/"):
            u = base + path
            rr = sess.get(u, headers=_headers(base + "/"), timeout=10, verify=False, allow_redirects=True)
            if rr.status_code == 200 and len(rr.text) > 5000 and "404" not in rr.text[:200].lower():
                return rr.url
    except Exception:
        return None
    return None


def _player_options(html: str) -> List[Tuple[str, str, str]]:
    opts = []
    for m in re.finditer(
        r'data-type=["\']([^"\']+)["\'][^>]*data-post=["\'](\d+)["\'][^>]*data-nume=["\']([^"\']+)["\']',
        html,
        re.I,
    ):
        opts.append((m.group(1), m.group(2), m.group(3)))
    if not opts:
        for m in re.finditer(
            r'data-post=["\'](\d+)["\'][^>]*data-type=["\']([^"\']+)["\'][^>]*data-nume=["\']([^"\']+)["\']',
            html,
            re.I,
        ):
            opts.append((m.group(2), m.group(1), m.group(3)))
    return opts


def _ajax_embed(sess: requests.Session, base: str, typ: str, post: str, nume: str) -> Optional[str]:
    ajax = urljoin(base + "/", "/wp-admin/admin-ajax.php")
    try:
        r = sess.post(
            ajax,
            headers={
                **_headers(base + "/"),
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            },
            data={"action": "doo_player_ajax", "post": post, "nume": nume, "type": typ},
            timeout=_TIMEOUT,
            verify=False,
        )
        if r.status_code != 200:
            return None
        try:
            j = r.json()
            emb = j.get("embed_url") or j.get("embed") or j.get("url")
            if emb:
                return emb.replace("\\/", "/")
        except Exception:
            pass
        m = re.search(r'(https?://[^"\'\s<>]+)', r.text)
        return m.group(1) if m else None
    except Exception:
        return None


def _resolve_embed_to_stream(embed: str, ref: str) -> Optional[Dict[str, Any]]:
    """Intenta hosters locales; si no, devuelve None."""
    try:
        from streams.providers.hosters import resolve_hoster_url

        streams = resolve_hoster_url(embed, referer=ref)
        if streams:
            low = streams[0].lower().split("?")[0]
            stype = "mp4" if low.endswith(".mp4") else "hls"
            return {
                "stream_url": streams[0],
                "stream_type": stype,
                "candidates": streams,
                "ref_url": ref,
            }
    except Exception as exc:
        print(f"[SOLOLATINO] hoster resolve error: {exc}", flush=True)
    # fallback: si el embed ya es m3u8/mp4
    low = embed.lower()
    if ".m3u8" in low or low.endswith(".mp4"):
        return {
            "stream_url": embed,
            "stream_type": "mp4" if ".mp4" in low else "hls",
            "candidates": [embed],
            "ref_url": ref,
        }
    return None


def _resolve_query(query: str, *, is_tv: bool = False) -> Dict[str, Any]:
    print(f"[SOLOLATINO] resolve q={query!r} tv={is_tv}")
    sess = requests.Session()
    tried = []
    for base in _MIRRORS:
        try:
            # warm
            sess.get(base + "/", headers=_headers(), timeout=10, verify=False)
            post_url = _find_post_url(sess, base, query)
            if not post_url:
                tried.append({"base": base, "error": "no_post"})
                continue
            page = sess.get(post_url, headers=_headers(base + "/"), timeout=_TIMEOUT, verify=False)
            if page.status_code != 200:
                tried.append({"base": base, "error": f"http_{page.status_code}"})
                continue
            opts = _player_options(page.text)
            if not opts:
                # iframes directos
                iframes = re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', page.text, re.I)
                for iframe in iframes[:6]:
                    src = urljoin(post_url, iframe)
                    if any(x in src for x in ("youtube", "facebook", "twitter")):
                        continue
                    got = _resolve_embed_to_stream(src, post_url)
                    if got:
                        print(f"[SOLOLATINO] OK iframe {urlparse(base).netloc}")
                        return ok_result(
                            "sololatino",
                            got["stream_url"],
                            stream_type=got.get("stream_type"),
                            candidates=got.get("candidates") or [got["stream_url"]],
                            ref_url=got.get("ref_url") or post_url,
                        )
                tried.append({"base": base, "error": "no_player_opts"})
                continue
            for typ, post, nume in opts[:8]:
                emb = _ajax_embed(sess, base, typ, post, nume)
                if not emb:
                    continue
                emb = urljoin(base + "/", emb)
                got = _resolve_embed_to_stream(emb, post_url)
                if got:
                    print(f"[SOLOLATINO] OK ajax {urlparse(base).netloc} post={post}")
                    return ok_result(
                        "sololatino",
                        got["stream_url"],
                        stream_type=got.get("stream_type"),
                        candidates=got.get("candidates") or [got["stream_url"]],
                        ref_url=got.get("ref_url") or post_url,
                    )
            tried.append({"base": base, "error": "hosters_fail"})
        except Exception as exc:
            tried.append({"base": base, "error": str(exc)[:80]})
    return empty_result("sololatino", error="sololatino_no_media", ref_url=_MIRRORS[0] + "/")


class SoloLatinoProvider:
    name = "sololatino"
    langs = ("es",)

    def resolve_movie(self, content_id: str) -> Dict[str, Any]:
        cid = (content_id or "").strip()
        title = None
        if cid.isdigit():
            title = _tmdb_title(cid, is_tv=False)
        if not title and not cid.startswith("tt") and not cid.isdigit():
            title = cid
        if not title:
            # imdb / unknown — no buscamos basura
            return empty_result(self.name, error="sololatino_needs_title", ref_url=_MIRRORS[0] + "/")
        return _resolve_query(title, is_tv=False)

    def resolve_tv(
        self, content_id: str, season: int = 1, episode: int = 1
    ) -> Dict[str, Any]:
        cid = (content_id or "").strip()
        title = None
        if cid.isdigit():
            title = _tmdb_title(cid, is_tv=True)
        if not title and not cid.startswith("tt") and not cid.isdigit():
            title = cid
        if not title:
            return empty_result(self.name, error="sololatino_needs_title", ref_url=_MIRRORS[0] + "/")
        # muchos WP usan "Title temporada N capitulo M" en búsqueda
        q = f"{title} {season}x{episode:02d}"
        return _resolve_query(q, is_tv=True)