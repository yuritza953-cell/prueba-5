#!/usr/bin/env python3
"""Servidor Kinora: sirve ./dist, proxy TMDB y resolución de streams.

Endpoints TMDB: /api/search, /api/detail, /api/season, /api/home, ...
Streams:        /api/stream, /api/providers

Variables de entorno:
  TMDB_API_KEY, STREAM_SIGN_KEY, STREAM_WORKER_BASE, ENABLE_UNLIMPLAY
"""
import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DIST = ROOT / "dist"
# Algunos entornos exportan PORT=0 (puerto aleatorio) y el servidor quedaria
# inalcanzable: solo se respeta un puerto explicito y valido.
_port = os.environ.get("PORT", "")
PORT = int(_port) if _port.isdigit() and int(_port) > 0 else 8000
POSTER = "https://image.tmdb.org/t/p/w500"
BACKDROP = "https://image.tmdb.org/t/p/w1280"
STILL = "https://image.tmdb.org/t/p/w300"

# TMDB no traduce todos los generos de TV en es-MX; se normalizan aqui.
GENRES_ES = {
    28: "Acción", 12: "Aventura", 16: "Animación", 35: "Comedia", 80: "Crimen",
    99: "Documental", 18: "Drama", 10751: "Familia", 14: "Fantasía", 36: "Historia",
    27: "Terror", 10402: "Música", 9648: "Misterio", 10749: "Romance",
    878: "Ciencia ficción", 10770: "Película de TV", 53: "Suspense", 10752: "Guerra",
    37: "Western", 10759: "Acción y aventura", 10762: "Infantil", 10763: "Noticias",
    10764: "Reality", 10765: "Ciencia ficción y fantasía", 10766: "Telenovela",
    10767: "Programa de entrevistas", 10768: "Guerra y política",
}


def load_env():
    f = ROOT / ".env"
    if not f.exists():
        return
    for line in f.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


def tmdb(path, **params):
    key = os.environ.get("TMDB_API_KEY", "")
    if not key:
        raise RuntimeError("Falta TMDB_API_KEY en el archivo .env")
    headers = {"Accept": "application/json"}
    if key.startswith("eyJ"):  # token de acceso v4
        headers["Authorization"] = f"Bearer {key}"
    else:  # API key v3
        params["api_key"] = key
    url = f"https://api.themoviedb.org/3/{path}?{urlencode(params)}"
    with urlopen(Request(url, headers=headers), timeout=10) as r:
        return json.load(r)


def wanted_audio(raw):
    """Normaliza el filtro de audio: 'all', 'sub' o 'dub'."""
    parts = {p.strip().lower() for p in (raw or "").split(",") if p.strip()}
    if "dub" in parts and "sub" not in parts:
        return "dub"
    if "sub" in parts and "dub" not in parts:
        return "sub"
    return "all"


def audio_tags(row, wanted):
    """TMDB no dice si un titulo trae doblaje o subtitulos, asi que lo aproximamos.

    Con un filtro explicito mostramos ese audio; con "Todos" marcamos ambos en
    los titulos populares (los que suelen llegar doblados) y solo subtitulos en
    el resto.
    """
    if wanted == "dub":
        return ["dub"]
    if wanted == "sub":
        return ["sub"]
    return ["sub", "dub"] if row.get("vote_count", 0) >= 500 else ["sub"]


def poster_url(path):
    return POSTER + path if path else None


def backdrop_url(path):
    return BACKDROP + path if path else None


def media_item(r, media, audio):
    """Normaliza un resultado de TMDB para que el frontend pinte tarjetas."""
    if media not in ("movie", "tv") or not r.get("poster_path"):
        return None
    # TMDB no tiene categoria "anime": animacion (16) + idioma original japones
    is_anime = 16 in r.get("genre_ids", []) and r.get("original_language") == "ja"
    date = r.get("release_date") or r.get("first_air_date") or ""
    return {
        "id": r["id"],
        "title": r.get("title") or r.get("name") or "",
        "kind": "anime" if is_anime else media,
        "media": media,
        "year": date[:4],
        "rating": round(r.get("vote_average") or 0, 1),
        "votes": r.get("vote_count") or 0,
        "poster": poster_url(r["poster_path"]),
        "backdrop": backdrop_url(r.get("backdrop_path")),
        "overview": r.get("overview") or "",
        "audio": audio_tags(r, audio),
        # Filtro original: define el idioma de la ficha, no solo las etiquetas.
        "audio_filter": audio,
        "url": f"https://www.themoviedb.org/{media}/{r['id']}",
    }


def media_rows(rows, media, audio):
    out = []
    for r in rows:
        item = media_item(r, r.get("media_type") or media, audio)
        if item:
            out.append(item)
    return out


def search(q, kind, audio, page=1):
    lang = "en-US" if audio == "sub" else "es-MX"
    endpoint = {"movie": "search/movie", "tv": "search/tv"}.get(kind, "search/multi")
    data = tmdb(endpoint, query=q, language=lang, include_adult="false", page=page)
    base = kind if kind in ("movie", "tv") else None
    out = media_rows(data.get("results", []), base, audio)
    if kind == "anime":
        out = [item for item in out if item["kind"] == "anime"]
    return out, data


def home(audio):
    """Portada del sitio: hero y filas, todo desde TMDB."""
    lang = "en-US" if audio == "sub" else "es-MX"
    trending = tmdb("trending/all/week", language=lang)
    popular = tmdb("movie/popular", language=lang)
    series = tmdb("trending/tv/week", language=lang)
    top = tmdb("movie/top_rated", language=lang)

    trend_items = media_rows(trending.get("results", []), None, audio)
    hero = [item for item in trend_items if item.get("backdrop")][:6] or trend_items[:6]
    return {
        "hero": hero,
        "rows": [
            {"key": "trending", "title": "Tendencias de hoy", "items": trend_items[:20]},
            {"key": "popular", "title": "Más populares", "items": media_rows(popular.get("results", []), "movie", audio)[:20]},
            {"key": "tv", "title": "Series en tendencia", "items": media_rows(series.get("results", []), "tv", audio)[:20]},
            {"key": "top", "title": "Mejor valoradas", "items": media_rows(top.get("results", []), "movie", audio)[:20]},
        ],
    }


def browse(media, category, page, audio):
    """Listados completos para los botones "Ver todos" y la navegacion."""
    media = "tv" if media == "tv" else "movie"
    lang = "en-US" if audio == "sub" else "es-MX"
    if category == "trending":
        data = tmdb(f"trending/{media}/week", language=lang, page=page)
    else:
        category = category if category in ("popular", "top_rated", "upcoming", "on_the_air") else "popular"
        data = tmdb(f"{media}/{category}", language=lang, page=page)
    return {
        "items": media_rows(data.get("results", []), media, audio),
        "page": data.get("page", page),
        "total_pages": data.get("total_pages", 1),
    }


def related(mid, media, audio):
    base = "tv" if media == "tv" else "movie"
    lang = "en-US" if audio == "sub" else "es-MX"
    data = tmdb(f"{base}/{mid}/recommendations", language=lang)
    return media_rows(data.get("results", []), base, audio)[:20]


def trailer_for(base, mid, lang):
    for language in (lang, "en-US"):
        data = tmdb(f"{base}/{mid}/videos", language=language)
        clips = [
            v
            for v in data.get("results", [])
            if v.get("site") == "YouTube" and v.get("key") and v.get("type") in ("Trailer", "Teaser")
        ]
        if clips:
            best = max(clips, key=lambda v: (v.get("type") == "Trailer", bool(v.get("official"))))
            return {
                "name": best.get("name") or "Trailer",
                "url": f"https://www.youtube.com/watch?v={best['key']}",
                "key": best["key"],
            }
    return None


def season_list(data):
    """Temporadas normales (sin especiales) para el selector T1, T2, ..."""
    return [
        {"number": s.get("season_number"), "name": s.get("name") or "", "count": s.get("episode_count") or 0}
        for s in data.get("seasons", [])
        if (s.get("season_number") or 0) > 0
    ]


def season(mid, number, audio):
    lang = "en-US" if audio == "sub" else "es-MX"
    data = tmdb(f"tv/{mid}/season/{number}", language=lang)
    out = []
    for e in data.get("episodes", []):
        still = e.get("still_path")
        out.append({
            "number": e.get("episode_number"),
            "name": e.get("name") or f"Episodio {e.get('episode_number')}",
            "overview": (e.get("overview") or "")[:220],
            "still": STILL + still if still else None,
            "runtime": e.get("runtime"),
            "air_date": (e.get("air_date") or "")[:10],
        })
    return {"name": data.get("name") or f"Temporada {number}", "episodes": out}


def episode_video(mid, season, episode, lang):
    """Video de un episodio concreto; si TMDB no tiene, devuelve None."""
    for language in (lang, "en-US"):
        try:
            data = tmdb(f"tv/{mid}/season/{season}/episode/{episode}/videos", language=language)
        except HTTPError as e:
            if e.code == 404:
                return None
            raise
        clips = [
            v
            for v in data.get("results", [])
            if v.get("site") == "YouTube" and v.get("key") and v.get("type") in ("Trailer", "Teaser", "Clip")
        ]
        if clips:
            best = max(clips, key=lambda v: (v.get("type") == "Trailer", bool(v.get("official"))))
            return {
                "name": best.get("name") or "Video",
                "key": best["key"],
                "url": f"https://www.youtube.com/watch?v={best['key']}",
            }
    return None


def first_review(base, mid, lang):
    data = tmdb(f"{base}/{mid}/reviews", language=lang)
    for r in data.get("results", []):
        content = (r.get("content") or "").strip()
        if len(content) < 80:
            continue
        return {
            "author": r.get("author") or "TMDB",
            "content": content[:600].rstrip() + ("…" if len(content) > 600 else ""),
        }
    return None


def detail(mid, media, audio):
    base = "tv" if media == "tv" else "movie"
    lang = "en-US" if audio == "sub" else "es-MX"
    data = tmdb(f"{base}/{mid}", language=lang)
    date = data.get("release_date") or data.get("first_air_date") or ""
    runtimes = data.get("episode_run_time") or []
    imdb_id = ""
    try:
        ext = tmdb(f"{base}/{mid}/external_ids")
        imdb_id = (ext.get("imdb_id") or "").strip()
    except Exception:
        imdb_id = ""
    return {
        "id": data.get("id", mid),
        "imdb_id": imdb_id or None,
        "kind": base,
        "title": data.get("title") or data.get("name") or "",
        "year": date[:4],
        "tagline": data.get("tagline") or "",
        "overview": data.get("overview") or "",
        "rating": round(data.get("vote_average") or 0, 1),
        "votes": data.get("vote_count") or 0,
        "poster": poster_url(data.get("poster_path")),
        "backdrop": backdrop_url(data.get("backdrop_path")) or poster_url(data.get("poster_path")),
        "genres": [GENRES_ES.get(g.get("id")) or g.get("name") for g in data.get("genres", []) if g.get("name")],
        "runtime": data.get("runtime") or (runtimes[0] if runtimes else None),
        "seasons": season_list(data) if base == "tv" else [],
        "audio": audio_tags(data, audio),
        "review": first_review(base, mid, lang),
        "trailer": trailer_for(base, mid, lang),
        "url": f"https://www.themoviedb.org/{base}/{mid}",
    }


class Handler(SimpleHTTPRequestHandler):

    # Silenciar ruido de scanners (/.env, /wp-*, terraform, etc.)
    _QUIET_404 = (
        ".env", ".git", "wp-", "phpinfo", "phpmyadmin", "actuator",
        "terraform", "docker-compose", "serverless", "aws.yml", "aws.yaml",
        "credentials", "config.json", ".aws", "symfony", "cgi-bin",
        "admin/", "debug", "actuator", "vendor/", "node_modules",
    )

    def log_message(self, fmt, *args):
        try:
            msg = fmt % args if args else str(fmt)
        except Exception:
            msg = str(fmt)
        # 404 de paths típicos de bots → no loguear
        if "404" in msg:
            path = (self.path or "").split("?", 1)[0].lower()
            if any(x in path for x in self._QUIET_404):
                return
            if path.count("/") > 3 and not path.startswith("/api/") and not path.startswith("/assets/"):
                # rutas raras profundas
                return
        return super().log_message(fmt, *args)

    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(DIST), **k)

    def send_head(self):
        """SPA: una ruta como /peliculas o /series/dune sirve index.html.

        Sin esto, recargar una ficha devolvía 404 y el flujo se perdía.
        """
        path = urlparse(self.path).path
        if not path.startswith("/api/") and not path.startswith("/assets/"):
            target = self.translate_path(self.path)
            name = os.path.basename(path)
            if not os.path.exists(target) and "." not in name:
                self.path = "/index.html"
        return super().send_head()

    def send_json(self, code, body):
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def send_error_json(self, e):
        if isinstance(e, HTTPError):
            if e.code == 404:
                return self.send_json(404, {"error": "TMDB no encontro ese titulo."})
            return self.send_json(502, {"error": f"TMDB respondio {e.code}. Revisa tu API key."})
        return self.send_json(500, {"error": str(e)})

    def do_GET(self):
        u = urlparse(self.path)
        api_paths = (
            "/api/search",
            "/api/detail",
            "/api/season",
            "/api/episode_video",
            "/api/home",
            "/api/browse",
            "/api/related",
            "/api/stream",
            "/api/providers",
            "/api/hls",
            "/api/subs",
            "/api/subs/download",
        )
        if u.path not in api_paths:
            return super().do_GET()
        p = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            # ── Streams ──────────────────────────────────────────────
            if u.path == "/api/hls":
                from streams.hls_local import handle_hls
                # query ya viene como p (primer valor por clave)
                return handle_hls(self, p)

            if u.path == "/api/subs":
                from streams.subtitles import search_subs, LANG_OPTIONS

                mid = (p.get("id") or p.get("tmdb") or "").strip()
                imdb = (p.get("imdb") or "").strip() or None
                media = p.get("media") or p.get("kind") or "movie"
                lang = (p.get("lang") or p.get("languages") or "es,en,pt-BR").strip()
                # No usar el nombre "season": sombrea la función global season() y rompe /api/season
                season_raw = p.get("season")
                episode_raw = p.get("episode")
                try:
                    season_i = int(season_raw) if season_raw not in (None, "") else None
                except ValueError:
                    season_i = None
                try:
                    episode_i = int(episode_raw) if episode_raw not in (None, "") else None
                except ValueError:
                    episode_i = None
                if not mid and not imdb:
                    return self.send_json(400, {"ok": False, "error": "Falta id TMDB o IMDB", "subs": []})
                result = search_subs(
                    tmdb_id=mid or None,
                    imdb_id=imdb,
                    media=media,
                    season=season_i,
                    episode=episode_i,
                    languages=lang,
                )
                return self.send_json(200 if result.get("ok") else 502, result)

            if u.path == "/api/subs/download":
                from streams.subtitles import download_sub

                fid = p.get("file_id") or p.get("id")
                try:
                    file_id = int(fid)
                except (TypeError, ValueError):
                    return self.send_json(400, {"ok": False, "error": "file_id inválido"})
                result = download_sub(file_id)
                if not result.get("ok"):
                    code = 429 if result.get("error") == "rate_limit_exceeded" else 502
                    return self.send_json(code, result)
                # devolver VTT como texto para <track>
                vtt = (result.get("vtt") or "").encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/vtt; charset=utf-8")
                self.send_header("Content-Length", str(len(vtt)))
                self.send_header("Cache-Control", "public, max-age=3600")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(vtt)
                return

            if u.path == "/api/providers":
                from streams.registry import list_providers, CHAINS

                return self.send_json(
                    200,
                    {"providers": list_providers(), "chains": CHAINS},
                )

            if u.path == "/api/stream":
                # id = TMDB. media=movie|tv. lang=es-MX|es-ES|en|fr|pt-BR.
                # season/episode solo para tv. imdb opcional.
                mid = (p.get("id") or "").strip()
                if not mid:
                    return self.send_json(400, {"error": "Falta el id TMDB", "ok": False})
                media = p.get("media") or p.get("kind") or "movie"
                # No aplastar es-MX / es-ES / fr / pt: normalize_audio_lang lo resuelve
                lang = (p.get("lang") or "es-MX").strip()
                try:
                    season_num = max(1, int(p.get("season", "1")))
                    episode_num = max(1, int(p.get("episode", "1")))
                except ValueError:
                    season_num, episode_num = 1, 1
                force_proxy = (p.get("force_proxy") or "").lower() in ("1", "true", "yes")
                try:
                    from streams import resolve_stream

                    result = resolve_stream(
                        media=media,
                        tmdb_id=mid,
                        lang=lang,
                        season=season_num,
                        episode=episode_num,
                        imdb_id=p.get("imdb") or None,
                        prefer=p.get("provider") or None,
                        force_proxy=force_proxy,
                    )
                except Exception as exc:
                    print(f"[stream] EXCEPTION: {type(exc).__name__}: {exc}")
                    result = {
                        "ok": False,
                        "error": f"resolve_exception: {exc}",
                        "error_class": "resolve_exception",
                        "streams": [],
                        "lang": lang,
                    }
                # Siempre 200 con ok true/false para que el front muestre el aviso de idioma
                return self.send_json(200, result)


            # ── TMDB ─────────────────────────────────────────────────
            if u.path == "/api/home":
                return self.send_json(200, home(wanted_audio(p.get("audio"))))

            if u.path == "/api/browse":
                try:
                    page = max(1, int(p.get("page", "1")))
                except ValueError:
                    page = 1
                return self.send_json(200, browse(p.get("media"), p.get("category"), page, wanted_audio(p.get("audio"))))

            if u.path == "/api/related":
                try:
                    mid = int(p.get("id", ""))
                except ValueError:
                    return self.send_json(400, {"error": "Falta el id del titulo"})
                media = p.get("media") or "movie"
                return self.send_json(200, {"items": related(mid, media, wanted_audio(p.get("audio")))})

            if u.path == "/api/detail":
                try:
                    mid = int(p.get("id", ""))
                except ValueError:
                    return self.send_json(400, {"error": "Falta el id del titulo"})
                media = p.get("media") or p.get("kind") or "movie"
                return self.send_json(200, detail(mid, "tv" if media == "tv" else "movie", wanted_audio(p.get("audio"))))

            if u.path == "/api/season":
                try:
                    mid = int(p.get("id", ""))
                    num = int(p.get("season", "1"))
                except ValueError:
                    return self.send_json(400, {"error": "Falta el id o la temporada"})
                return self.send_json(200, season(mid, num, wanted_audio(p.get("audio"))))

            if u.path == "/api/episode_video":
                try:
                    mid = int(p.get("id", ""))
                    num = int(p.get("season", "1"))
                    ep = int(p.get("episode", "1"))
                except ValueError:
                    return self.send_json(400, {"error": "Faltan el id, la temporada o el episodio"})
                lang = "en-US" if wanted_audio(p.get("audio")) == "sub" else "es-MX"
                video = episode_video(mid, num, ep, lang)
                if not video:
                    return self.send_json(404, {"error": "Ese episodio no tiene video"})
                return self.send_json(200, video)

            q = p.get("q", "").strip()
            if not q:
                return self.send_json(400, {"error": "Escribe algo para buscar"})
            try:
                page = max(1, int(p.get("page", "1")))
            except ValueError:
                page = 1
            results, data = search(q, p.get("type", "all"), wanted_audio(p.get("audio")), page)
            return self.send_json(200, {
                "results": results,
                "page": data.get("page", page),
                "total_pages": data.get("total_pages", 1),
            })
        except HTTPError as e:
            self.send_error_json(e)
        except (URLError, RuntimeError) as e:
            self.send_error_json(e)


if __name__ == "__main__":
    load_env()
    print(f"Kinora en http://localhost:{PORT}")
    ThreadingHTTPServer(("", PORT), Handler).serve_forever()