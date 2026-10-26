"""
VidSrc stream resolver (English path).

Cadena real:
  1. GET vidsrc.sh/vs_src.php → { src: stellar.../embed/...?vs=TOKEN }
  2. GET landing embed → CFG.playerUrl
  3. GET player page → CONFIG { api, apiToken }
  4. GET data.vidsrc.sh/api.php?...&stream_urls&api_token=...
       → data.stream_urls (ChaCha20+WASM) + vs.wasm_url
  5. Descifrar stream_urls con Node/WebAssembly
  6. GET {cdn_origin}/generate.php → host token (JWT)
  7. stream = m3u8 + ?token=JWT
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import tempfile
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urljoin, urlparse

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from .constants import BASE_URL, EMBED_MOVIE, EMBED_TV, HTTP_TIMEOUT, VS_SRC

_BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_SESSION = requests.Session()
_SESSION.headers.update(_BROWSER)
_TIMEOUT = (8, max(HTTP_TIMEOUT, 30))
_PLAYER_HOST = "https://stellarconductornexus.com"


def _unique(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for x in items:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


# Mirrors de vs_src (misma familia stellar / token vs=)
_VS_SRC_MIRRORS = (
    VS_SRC,  # vidsrc.sh
    "https://hnembed.cc/vs_src.php",  # hnembed (Fase 2)
    "https://vidsrc.sh/vs_src.php",
)


def _vs_src(content_type: str, content_id: str, season: int = 1, episode: int = 1) -> Optional[str]:
    params: Dict[str, Any] = {"type": content_type, "id": str(content_id)}
    if content_type == "tv":
        params["season"] = season
        params["episode"] = episode
    last_err: Optional[str] = None
    for endpoint in _VS_SRC_MIRRORS:
        try:
            ref = endpoint.rsplit("/", 1)[0] + "/"
            r = _SESSION.get(
                endpoint,
                params=params,
                headers={**_BROWSER, "Referer": ref, "Accept": "application/json"},
                timeout=_TIMEOUT,
            )
            if r.status_code >= 400:
                last_err = f"http_{r.status_code}"
                continue
            data = r.json()
            src = data.get("src") if isinstance(data, dict) else None
            if src and str(src).startswith("http"):
                print(f"[VIDSRC] vs_src OK via {endpoint.split('/')[2]} {str(src)[:80]}")
                return str(src)
            last_err = f"empty:{data}"
        except Exception as exc:
            last_err = str(exc)
            continue
    print(f"[VIDSRC] vs_src failed all mirrors last={last_err}")
    return None


def _extract_player_url(landing_html: str, landing_url: str) -> Optional[str]:
    m = re.search(r'"playerUrl"\s*:\s*"([^"]+)"', landing_html)
    if not m:
        return None
    pu = m.group(1).replace("\\u0026", "&").replace("\\/", "/")
    if pu.startswith("/"):
        base = f"{urlparse(landing_url).scheme}://{urlparse(landing_url).netloc}"
        pu = base + pu
    return pu


def _extract_config(player_html: str) -> Optional[Dict[str, Any]]:
    idx = player_html.find("CONFIG = {")
    if idx < 0:
        idx = player_html.find("CONFIG=")
    if idx < 0:
        return None
    i = player_html.find("{", idx)
    if i < 0:
        return None
    depth = 0
    for j in range(i, min(i + 12000, len(player_html))):
        ch = player_html[j]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                blob = player_html[i : j + 1].replace("\\u0026", "&")
                try:
                    return json.loads(blob)
                except Exception:
                    return None
    return None


def _decrypt_stream_urls(enc_b64: str, wasm_bytes: bytes) -> List[str]:
    """Descifra stream_urls con el WASM de VidSrc vía Node."""
    try:
        with tempfile.TemporaryDirectory() as td:
            enc_path = os.path.join(td, "enc.txt")
            wasm_path = os.path.join(td, "vs.wasm")
            js_path = os.path.join(td, "dec.js")
            with open(enc_path, "w", encoding="utf-8") as f:
                f.write(enc_b64.strip())
            with open(wasm_path, "wb") as f:
                f.write(wasm_bytes)
            js = f"""
const fs = require('fs');
const encB64 = fs.readFileSync({enc_path!r}, 'utf8').trim();
const wasmBytes = fs.readFileSync({wasm_path!r});
(async () => {{
  const mod = await WebAssembly.compile(wasmBytes);
  const inst = await WebAssembly.instantiate(mod, {{}});
  const ex = inst.exports;
  const enc = Buffer.from(encB64, 'base64');
  const ptr = ex.alloc(enc.length);
  new Uint8Array(ex.memory.buffer, ptr, enc.length).set(enc);
  const outLen = ex.decrypt(ptr, enc.length);
  const txt = new TextDecoder().decode(new Uint8Array(ex.memory.buffer, ptr + 12, outLen));
  process.stdout.write(txt);
}})().catch(e => {{ console.error(String(e)); process.exit(1); }});
"""
            with open(js_path, "w", encoding="utf-8") as f:
                f.write(js)
            out = subprocess.check_output(
                ["node", js_path],
                timeout=25,
                stderr=subprocess.STDOUT,
            )
            text = out.decode("utf-8", errors="replace")
            return [ln.strip() for ln in text.splitlines() if ln.strip().startswith("http")]
    except FileNotFoundError:
        print("[VIDSRC] node no disponible para descifrar WASM")
        return []
    except subprocess.CalledProcessError as exc:
        print(f"[VIDSRC] decrypt fail: {exc.output[:200] if exc.output else exc}")
        return []
    except Exception as exc:
        print(f"[VIDSRC] decrypt error: {exc}")
        return []


def _host_token(stream_url: str, referer: str) -> str:
    """GET {origin}/generate.php → JWT del CDN."""
    try:
        p = urlparse(stream_url)
        origin = f"{p.scheme}://{p.hostname}"
        r = _SESSION.get(
            origin + "/generate.php",
            headers={
                **_BROWSER,
                "Referer": referer or _PLAYER_HOST + "/",
                "Origin": _PLAYER_HOST,
                "Accept": "*/*",
            },
            timeout=_TIMEOUT,
        )
        if not r.ok:
            print(f"[VIDSRC] generate.php {r.status_code}")
            return ""
        t = (r.text or "").strip()
        if t.startswith("{"):
            try:
                j = r.json()
                t = str(j.get("token") or j.get("data") or j.get("result") or t)
            except Exception:
                pass
        return t
    except Exception as exc:
        print(f"[VIDSRC] generate.php error: {exc}")
        return ""


def _apply_token(url: str, token: str) -> str:
    if not token:
        return url
    if "__TOKEN__" in url:
        return url.replace("__TOKEN__", token)
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}token={quote(token)}"


def _probe(url: str, referer: str) -> bool:
    try:
        r = _SESSION.get(
            url,
            headers={
                **_BROWSER,
                "Referer": referer or _PLAYER_HOST + "/",
                "Origin": _PLAYER_HOST,
                "Accept": "*/*",
            },
            timeout=(4, 6),
            stream=True,
            verify=False,
        )
        chunk = b""
        for part in r.iter_content(400):
            chunk += part
            if len(chunk) >= 200:
                break
        if r.status_code >= 400:
            return False
        text = chunk[:120].decode("utf-8", errors="ignore")
        return "#EXTM3U" in text or "video" in (r.headers.get("Content-Type") or "")
    except Exception:
        return False


def _resolve_chain(content_type: str, content_id: str, season: int = 1, episode: int = 1) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "stream_url": None,
        "stream_type": None,
        "candidates": [],
        "providers": [],
        "embed_url": None,
        "error": None,
        "source": "vidsrc",
    }

    landing = _vs_src(content_type, content_id, season, episode)
    if not landing:
        result["error"] = "vs_src_failed"
        return result
    result["providers"].append(landing)

    try:
        r = _SESSION.get(
            landing,
            headers={**_BROWSER, "Referer": BASE_URL + "/", "Accept": "text/html"},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        landing_html = r.text or ""
    except Exception as exc:
        result["error"] = f"landing_fetch: {exc}"
        return result

    player_url = _extract_player_url(landing_html, landing)
    if not player_url:
        result["error"] = "player_url_missing"
        return result
    result["providers"].append(player_url)
    result["ref_url"] = player_url  # el CDN valida este Referer/Origin (igual que el probe)
    print(f"[VIDSRC] player {player_url[:90]}")

    try:
        pr = _SESSION.get(
            player_url,
            headers={**_BROWSER, "Referer": landing, "Accept": "text/html"},
            timeout=_TIMEOUT,
        )
        pr.raise_for_status()
        player_html = pr.text or ""
    except Exception as exc:
        result["error"] = f"player_fetch: {exc}"
        return result

    cfg = _extract_config(player_html)
    if not cfg or not cfg.get("api"):
        result["error"] = "config_missing"
        return result

    api = str(cfg["api"])
    api_token = str(cfg.get("apiToken") or "")
    if api_token:
        api = api + ("&" if "?" in api else "?") + "api_token=" + quote(api_token)

    try:
        ar = _SESSION.get(
            api,
            headers={
                **_BROWSER,
                "Referer": player_url,
                "Origin": _PLAYER_HOST,
                "Accept": "application/json",
            },
            timeout=_TIMEOUT,
        )
        ar.raise_for_status()
        payload = ar.json()
    except Exception as exc:
        result["error"] = f"stream_api: {exc}"
        return result

    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        result["error"] = "stream_api_invalid"
        return result

    stream_field = data.get("stream_urls")
    raw_urls: List[str] = []

    if isinstance(stream_field, list):
        raw_urls = [str(u) for u in stream_field if str(u).startswith("http")]
    elif isinstance(stream_field, str) and stream_field.strip():
        vs = payload.get("vs") or {}
        wasm_url = vs.get("wasm_url") if isinstance(vs, dict) else None
        if not wasm_url:
            result["error"] = "wasm_url_missing"
            return result
        try:
            wr = _SESSION.get(wasm_url, timeout=_TIMEOUT)
            wr.raise_for_status()
            wasm_bytes = wr.content
        except Exception as exc:
            result["error"] = f"wasm_fetch: {exc}"
            return result
        raw_urls = _decrypt_stream_urls(stream_field, wasm_bytes)
        print(f"[VIDSRC] decrypted {len(raw_urls)} urls")
    else:
        result["error"] = "no_stream_urls"
        return result

    if not raw_urls:
        result["error"] = "decrypt_empty"
        return result

    # Token por host + probe (early exit al primer OK)
    working: List[str] = []
    token_cache: Dict[str, str] = {}
    for raw in raw_urls[:5]:
        origin = f"{urlparse(raw).scheme}://{urlparse(raw).hostname}"
        if origin not in token_cache:
            token_cache[origin] = _host_token(raw, player_url)
        stamped = _apply_token(raw, token_cache[origin])
        if _probe(stamped, player_url):
            working.append(stamped)
            print(f"[VIDSRC] probe OK {stamped[:90]}")
            break  # primer usable basta
        else:
            print(f"[VIDSRC] probe FAIL {stamped[:90]}")

    candidates = working or [
        _apply_token(u, token_cache.get(f"{urlparse(u).scheme}://{urlparse(u).hostname}", ""))
        for u in raw_urls
    ]
    result["candidates"] = _unique(candidates)[:2]
    if working:
        result["stream_url"] = working[0]
        result["stream_type"] = "hls"
    elif candidates:
        result["stream_url"] = candidates[0]
        result["stream_type"] = "hls"
        result["error"] = "unprobed_fallback"
    else:
        result["error"] = "no_stream_found"
    return result


def resolve_movie(content_id: str) -> Dict[str, Any]:
    print(f"[VIDSRC] resolve movie {content_id}")
    t0 = time.time()
    data = _resolve_chain("movie", content_id)
    data["embed_url"] = EMBED_MOVIE.format(content_id=content_id)
    data["source"] = "vidsrc"
    print(
        f"[VIDSRC] done movie in {time.time()-t0:.1f}s "
        f"url={(data.get('stream_url') or '')[:80]} err={data.get('error')}"
    )
    return data


def resolve_tv(content_id: str, season: int = 1, episode: int = 1) -> Dict[str, Any]:
    print(f"[VIDSRC] resolve tv {content_id} S{season}E{episode}")
    t0 = time.time()
    data = _resolve_chain("tv", content_id, season, episode)
    data["embed_url"] = EMBED_TV.format(
        content_id=content_id, season=season, episode=episode
    )
    data["source"] = "vidsrc"
    print(
        f"[VIDSRC] done tv in {time.time()-t0:.1f}s "
        f"url={(data.get('stream_url') or '')[:80]} err={data.get('error')}"
    )
    return data