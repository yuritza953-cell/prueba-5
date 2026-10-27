"""
Registro de providers y cadenas por idioma.

Política (no mezclar audio):
  • es → videoapi → embed69 → sololatino → playlatinsrc → unlimplay (opcional)
  • en → vidsrc → vidapi → vixsrc → vidzee → vidfast → vaplayer → vidlink

Añadir un provider:
  1. streams/providers/mi_provider.py  (clase name + langs + resolve_*)
  2. Registrarlo en _BUILTIN y en CHAINS abajo.
"""
from __future__ import annotations
import time

from concurrent.futures import ThreadPoolExecutor, as_completed

import os
import threading
from typing import Any, Dict, List, Optional

from streams.base import empty_result
from streams.validate import is_bad_stream_url


def _es_chain() -> List[str]:
    # Prioridad: es-419 (Latino)
    chain = [
        "videoapi",
        "cuevana",
        "moviedays",
        "lamovie",
        "embed69",
        "sololatino",
        "playlatinsrc",
        "unlimplay",
    ]
    # Opt-out solo con ENABLE_UNLIMPLAY=0
    ulp = (os.environ.get("ENABLE_UNLIMPLAY") or "1").lower()
    if ulp in ("0", "false", "no", "off"):
        chain = [p for p in chain if p != "unlimplay"]
    if (os.environ.get("CINEPRO_BASE_URL") or "").strip():
        chain.append("cinepro")
    return chain


def _en_chain() -> List[str]:
    # Fase 2: vidsrc + twoembed (2embed.skin → hosters/vidsrc) + vidapi family
    chain = ["vidsrc", "twoembed", "vidapi", "vixsrc", "vidzee", "vidfast", "vaplayer", "vidlink"]
    if (os.environ.get("CINEPRO_BASE_URL") or "").strip():
        chain.append("cinepro")
    return chain


def _es_es_chain() -> List[str]:
    """Castellano (España). Tioplus / SoloLatino / Cuevana prioritarios."""
    chain = [
        "tioplus",
        "sololatino",
        "cuevana",
        "embed69",
        "videoapi",
        "moviedays",
        "lamovie",
        "playlatinsrc",
        "unlimplay",
    ]
    ulp = (os.environ.get("ENABLE_UNLIMPLAY") or "1").lower()
    if ulp in ("0", "false", "no", "off"):
        chain = [p for p in chain if p != "unlimplay"]
    if (os.environ.get("CINEPRO_BASE_URL") or "").strip():
        chain.append("cinepro")
    return chain


def _sub_chain() -> List[str]:
    """Subtitulado / multi: cuevana / tioplus / vidsrc / twoembed."""
    return ["cuevana", "tioplus", "vidsrc", "twoembed", "videoapi"]


def _fr_chain() -> List[str]:
    # Fase 3: cobertura internacional vía family EN (links limpios).
    # Providers FR dedicados (Nuvio FR) se irán sumando después.
    chain = ["vidsrc", "twoembed", "vidapi", "vixsrc", "vidlink"]
    if (os.environ.get("CINEPRO_BASE_URL") or "").strip():
        chain.append("cinepro")
    return chain


def _pt_chain() -> List[str]:
    # Português (BR/PT) — misma base internacional + latinos que a veces traen PT
    chain = [
        "videoapi", "cuevana", "moviedays", "playlatinsrc",
        "vidsrc", "twoembed", "vidapi", "vidlink",
    ]
    if (os.environ.get("CINEPRO_BASE_URL") or "").strip():
        chain.append("cinepro")
    return chain


# Claves canónicas de audio (no subtítulos)
CHAINS: Dict[str, List[str]] = {
    "es": _es_chain(),       # alias de es-MX (Latino)
    "es-MX": _es_chain(),    # Español latino
    "es-ES": _es_es_chain(), # Castellano
    "sub": _sub_chain(),     # Subtitulado
    "en": _en_chain(),
    "fr": _fr_chain(),
    "pt": _pt_chain(),
    "pt-BR": _pt_chain(),
}


# Idiomas ofrecidos en el selector del player (orden UI)
AUDIO_LANGS: List[Dict[str, str]] = [
    {"code": "es-MX", "label_es": "Español (Latino)", "label_en": "Spanish (Latin)"},
    {"code": "es-ES", "label_es": "Español (Castellano)", "label_en": "Spanish (Spain)"},
    {"code": "en", "label_es": "English", "label_en": "English"},
    {"code": "fr", "label_es": "Français", "label_en": "French"},
    {"code": "pt-BR", "label_es": "Português (Brasil)", "label_en": "Portuguese (Brazil)"},
]


def normalize_audio_lang(lang: Optional[str]) -> str:
    """Normaliza query lang → clave de CHAINS."""
    s = (lang or "es-MX").strip().lower().replace("_", "-")
    if s in ("es-mx", "es-419", "es-lat", "es-la", "latino", "lat"):
        return "es-MX"
    if s in ("es-es", "es-es", "castellano", "spain", "es-eu"):
        return "es-ES"
    if s in ("es", "spa", "spanish"):
        return "es-MX"  # por defecto latino
    if s.startswith("en"):
        return "en"
    if s.startswith("fr"):
        return "fr"
    if s in ("pt-br", "pt-br", "ptbr", "br"):
        return "pt-BR"
    if s.startswith("pt"):
        return "pt-BR"
    if s in CHAINS:
        return s if s in ("es-MX", "es-ES", "en", "fr", "pt-BR") else "es-MX"
    return "es-MX"


def chain_for_lang(lang: str) -> List[str]:
    key = normalize_audio_lang(lang)
    return list(CHAINS.get(key) or CHAINS.get("es-MX") or [])


def _load_builtin() -> Dict[str, type]:
    """Import perezoso por provider: si uno falla, el resto sigue vivo."""
    mapping = {
        "videoapi": "streams.providers.videoapi:VideoApiProvider",
        "cuevana": "streams.providers.cuevana:CuevanaProvider",
        "tioplus": "streams.providers.tioplus:TioPlusProvider",
        "moviedays": "streams.providers.moviedays:MovieDaysProvider",
        "lamovie": "streams.providers.lamovie:LaMovieProvider",
        "vixsrc": "streams.providers.vixsrc:VixSrcProvider",
        "vidapi": "streams.providers.vidapi:VidApiProvider",
        "vidfast": "streams.providers.vidfast:VidFastProvider",
        "vidzee": "streams.providers.vidzee:VidZeeProvider",
        "vaplayer": "streams.providers.vaplayer:VaPlayerProvider",
        "vidlink": "streams.providers.vidlink:VidLinkProvider",
        "embed69": "streams.providers.embed69:Embed69Provider",
        "sololatino": "streams.providers.sololatino:SoloLatinoProvider",
        "playlatinsrc": "streams.providers.playlatinsrc:PlayLatinProvider",
        "vidsrc": "streams.providers.vidsrc:VidSrcProvider",
        "hnembed": "streams.providers.hnembed:HnEmbedProvider",
        "twoembed": "streams.providers.twoembed:TwoEmbedProvider",
        "unlimplay": "streams.providers.unlimplay:UnlimPlayProvider",
        "cinepro": "streams.providers.cinepro:CineProProvider",
    }
    out: Dict[str, type] = {}
    for name, path in mapping.items():
        mod_name, cls_name = path.split(":")
        try:
            mod = __import__(mod_name, fromlist=[cls_name])
            out[name] = getattr(mod, cls_name)
        except Exception as exc:  # noqa: BLE001
            print(f"[providers] SKIP {name}: {type(exc).__name__}: {exc}", flush=True)
    print(f"[providers] loaded={list(out.keys())}", flush=True)
    return out


_BUILTIN: Optional[Dict[str, type]] = None
_builtin_lock = threading.Lock()
_instances: Dict[str, Any] = {}


def _builtin() -> Dict[str, type]:
    global _BUILTIN
    if _BUILTIN is not None:
        return _BUILTIN
    with _builtin_lock:
        if _BUILTIN is None:
            _BUILTIN = _load_builtin()
        return _BUILTIN


def get_provider(name: str):
    name = (name or "").lower().strip()
    if name not in _instances:
        try:
            cls = _builtin().get(name)
        except Exception as exc:  # noqa: BLE001
            print(f"[providers] _builtin() error: {type(exc).__name__}: {exc}", flush=True)
            return None
        if cls is None:
            return None
        try:
            _instances[name] = cls()
        except Exception as exc:  # noqa: BLE001
            print(f"[providers] init {name} fail: {type(exc).__name__}: {exc}", flush=True)
            return None
    return _instances[name]


def list_providers() -> List[Dict[str, Any]]:
    out = []
    for name, cls in _builtin().items():
        inst = get_provider(name)
        out.append(
            {
                "name": name,
                "langs": list(getattr(inst, "langs", ())),
                "enabled_es": name in CHAINS.get("es", []),
                "enabled_en": name in CHAINS.get("en", []),
            }
        )
    return out


def lang_from_source(source: str) -> str:
    s = (source or "").lower().strip()
    if s in (
        "vidsrc", "en", "english", "eng", "vaplayer", "vidlink",
        "vidapi", "vixsrc", "vidzee", "vidfast", "hnembed", "twoembed", "2embed",
    ):
        return "en"
    return "es"


def normalize_source(source: str) -> str:
    s = (source or "").lower().strip()
    aliases = {
        "en": "vidsrc", "english": "vidsrc", "eng": "vidsrc",
        "vidapi": "vidapi", "vaplayer.ru": "vidapi", "brightpath": "vidapi",
        "vixsrc": "vixsrc", "vix": "vixsrc",
        "vidzee": "vidzee",
        "vidfast": "vidfast",
        "sololatino": "sololatino", "seriesmetro": "sololatino",
        "lamovie": "lamovie", "moviedays": "moviedays", "md": "moviedays",
        "vaplayer": "vaplayer", "va": "vaplayer",
        "vidlink": "vidlink", "vlink": "vidlink",
        "videoapi": "videoapi", "videoapi.la": "videoapi", "vimeos": "videoapi",
        "embed69": "embed69",
        "playlatinsrc": "playlatinsrc", "playlatin": "playlatinsrc",
        "latinsrc": "playlatinsrc", "latino": "playlatinsrc",
        "unlimplay": "unlimplay", "ulp": "unlimplay",
        "vidsrc": "vidsrc",
    }
    if s in aliases:
        return aliases[s]
    return (CHAINS.get("es-MX") or CHAINS.get("es") or ["videoapi"])[0]


def _ids_for_provider(pname: str, content_id: str, alt_id: Optional[str]) -> List[str]:
    """Algunos providers piden IMDb (tt…), otros TMDB numérico."""
    cid = str(content_id).strip()
    alt = str(alt_id).strip() if alt_id else ""
    ids: List[str] = []

    def add(x: str) -> None:
        if x and x not in ids:
            ids.append(x)

    if pname == "unlimplay":
        # Preferir IMDb (el embed de UnlimPlay lo resuelve mejor)
        if alt.startswith("tt"):
            add(alt)
        if cid.startswith("tt"):
            add(cid)
        add(cid)
        if alt:
            add(alt)
    elif pname == "vaplayer":
        if cid.startswith("tt"):
            add(cid)
        if alt.startswith("tt"):
            add(alt)
        add(cid)
        if alt:
            add(alt)
    elif pname in ("vidlink", "videoapi", "vidapi", "vixsrc", "vidzee", "vidfast", "moviedays", "lamovie"):
        if cid.isdigit():
            add(cid)
        if alt.isdigit():
            add(alt)
        add(cid)
        if alt:
            add(alt)
    elif pname == "sololatino":
        # SoloLatino busca por título vía TMDB id numérico
        if cid.isdigit():
            add(cid)
        if alt.isdigit():
            add(alt)
        if not cid.isdigit() and not (alt or "").isdigit():
            add(cid)
    else:
        add(cid)
        if alt and alt != cid:
            add(alt)
    return ids



# Taxonomía canónica de errores
PROVIDER_DOWN = "ProviderDown"
PROVIDER_BLOCKED = "ProviderBlocked"
TOKEN_EXPIRED = "TokenExpired"
NO_SOURCE = "NoSource"

# Circuit breaker por provider/host (30–60 s) ante ProviderDown / ProviderBlocked
_CIRCUIT: Dict[str, float] = {}
_CIRCUIT_LOCK = threading.Lock()
_CIRCUIT_TTL = float(os.environ.get("PROVIDER_CIRCUIT_TTL", "45"))  # 45 segundos default


def _circuit_open(name: str) -> bool:
    with _CIRCUIT_LOCK:
        until = _CIRCUIT.get(name) or 0.0
        return until > time.time()


def _circuit_trip(name: str, cls: str) -> None:
    """Dispara el circuit breaker (30–60 s) ante caída o bloqueo, no ante NoSource."""
    if cls in (PROVIDER_DOWN, PROVIDER_BLOCKED, "blocked_cf", "timeout"):
        with _CIRCUIT_LOCK:
            _CIRCUIT[name] = time.time() + _CIRCUIT_TTL
            print(f"[providers] circuit OPEN {name} {int(_CIRCUIT_TTL)}s class={cls}", flush=True)


def _classify_error(err: Optional[str], detail: str = "") -> str:
    """Taxonomía estable de errores para UI y logs: ProviderDown, ProviderBlocked, TokenExpired, NoSource."""
    e = (err or "").lower()
    d = (detail or "").lower()
    blob = e + " " + d
    if any(x in blob for x in ("expired", "caducado", "token_expired")):
        return TOKEN_EXPIRED
    if any(x in blob for x in ("challenge", "cloudflare", "cf-", "just a moment", "blocked_cf", "verificando", "403", "forbidden", "providerblocked")):
        return PROVIDER_BLOCKED
    if any(x in blob for x in ("timeout", "timed out", "deadline", "502", "503", "504", "connection", "refused", "resolve_exception", "provider_missing", "providerdown")):
        return PROVIDER_DOWN
    if any(x in blob for x in ("needs_imdb", "needs_tmdb", "needs_id", "not_found", "no_sources", "404", "not_in_catalog", "source_not_found", "dead", "decoy", "not_m3u", "empty", "no_stream", "nosource")):
        return NO_SOURCE
    if e:
        return e
    return NO_SOURCE


def _try_one_provider(
    pname: str,
    content_id: str,
    alt_id: Optional[str],
    is_tv: bool,
    season: int,
    episode: int,
) -> Dict[str, Any]:
    if _circuit_open(pname):
        print(f"[providers] {pname} circuit-open skip", flush=True)
        return empty_result(pname, error="circuit_open")
    prov = get_provider(pname)
    if prov is None:
        print(f"[providers] {pname} missing/unavailable", flush=True)
        return empty_result(pname, error="provider_missing")

    last = empty_result(pname, error="no_stream")
    for ident in _ids_for_provider(pname, content_id, alt_id):
        try:
            if is_tv:
                data = prov.resolve_tv(ident, season, episode)
            else:
                data = prov.resolve_movie(ident)
        except Exception as exc:  # noqa: BLE001
            print(f"[providers] {pname}/{ident} excepción: {exc}")
            data = empty_result(pname, error="resolve_exception")
            data["error_detail"] = f"{type(exc).__name__}: {exc}"[:160]
            data["error_class"] = _classify_error("resolve_exception", data["error_detail"])
            last = data
            # fallo transitorio → probar otro id, no matar provider
            continue

        data = data or empty_result(pname, error="no_stream")
        err = data.get("error")
        data["error_class"] = _classify_error(err, data.get("error_detail") or "")
        if err:
            _circuit_trip(pname, data["error_class"])
        data["resolved_id"] = ident

        if data.get("stream_url") and not err and not is_bad_stream_url(data.get("stream_url") or ""):
            # Validar stream_url y candidatos antes de dar al provider por ganador
            from streams.validate import validate_stream

            ref = data.get("ref_url") or ""
            stype = data.get("stream_type") or "hls"
            cands = list(data.get("candidates") or [])
            if data["stream_url"] not in cands:
                cands.insert(0, data["stream_url"])

            valid_cands: List[str] = []
            for u in cands:
                ok, verr = validate_stream(u, stream_type=stype, ref=ref)
                if ok:
                    valid_cands.append(u)
                else:
                    print(f"[providers] {pname} stream probe fail ({verr}): {u[:70]}", flush=True)

            if valid_cands:
                data["stream_url"] = valid_cands[0]
                data["candidates"] = valid_cands
                return data

            # Todos los candidatos fallaron probe: se trata como fallo del provider para no ganar con stream muerto
            print(f"[providers] {pname} todos los candidatos fallaron validación, probando siguiente", flush=True)
            data["stream_url"] = None
            data["candidates"] = []
            data["error"] = "validation_failed"
            data["error_class"] = _classify_error("dead_file", "probe failed")
            _circuit_trip(pname, data["error_class"])
            last = data
            continue

        last = data
        # needs_id → probar otro ident; not_in_catalog → salir del provider
        if data["error_class"] in ("not_in_catalog", "blocked_cf"):
            break
        # timeout / resolve_exception → reintentar con otro id
        continue
    return last


def resolve_with_chain(
    *,
    lang: str,
    content_type: str,
    content_id: str,
    season: int = 1,
    episode: int = 1,
    prefer: Optional[str] = None,
    alt_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Providers en paralelo. En cuanto el provider de mayor prioridad con éxito
    termina (y los de mayor prioridad ya fallaron o no existen), devolvemos
    sin esperar a UnlimPlay/CF ni hosters lentos.
    """
    lang = normalize_audio_lang(lang)
    chain = chain_for_lang(lang)
    print(f"[providers] chain lang={lang} providers={chain}", flush=True)
    if not chain:
        print(f"[providers] EMPTY chain for lang={lang} CHAINS_keys={list(CHAINS.keys())}", flush=True)
        return empty_result("none", error="no_providers_for_lang")

    if prefer and prefer in chain:
        chain = [prefer] + [p for p in chain if p != prefer]

    is_tv = (content_type or "").lower() in ("tv", "anime", "serie", "series")
    results: Dict[str, Dict[str, Any]] = {}
    order = {name: i for i, name in enumerate(chain)}

    max_workers = min(6, max(1, len(chain)))
    pool = ThreadPoolExecutor(max_workers=max_workers)
    first_success_ts: Optional[float] = None
    GRACE_SEC = float(os.environ.get("STREAM_PROVIDER_GRACE_SEC", "1.5"))

    try:
        futs = {
            pool.submit(
                _try_one_provider, pname, content_id, alt_id, is_tv, season, episode
            ): pname
            for pname in chain
        }
        pending = set(futs.keys())

        for fut in as_completed(futs):
            pname = futs[fut]
            pending.discard(fut)
            try:
                data = fut.result()
            except Exception as exc:  # noqa: BLE001
                data = empty_result(pname, error="resolve_exception")
                data["error_detail"] = str(exc)[:160]
                data["error_class"] = "resolve_exception"
            results[pname] = data

            # ¿Hay algún éxito entre los ya terminados?
            best = None
            best_i = 10**9
            for name, res in results.items():
                if res.get("stream_url") and not res.get("error") and not is_bad_stream_url(res.get("stream_url") or ""):
                    i = order.get(name, 10**9)
                    if i < best_i:
                        best = res
                        best_i = i

            if best is None:
                continue

            if first_success_ts is None:
                first_success_ts = time.time()

            # Si ya ganó el de mayor prioridad absoluta de la cadena, salida inmediata
            if best_i == 0:
                break

            # ¿Queda algún provider MÁS prioritario aún corriendo?
            higher_running = any(
                order[futs[f]] < best_i for f in pending if futs[f] in order
            )
            if not higher_running:
                break

            # Si hay un provider de mayor prioridad corriendo, esperar como máximo GRACE_SEC (1.5s)
            # para no hacer esperar al usuario 20-50s por un provider lento/colgado
            if (time.time() - first_success_ts) >= GRACE_SEC:
                print(
                    f"[providers] Ventana de gracia ({GRACE_SEC}s) agotada con stream válido de {best.get('provider')}. "
                    f"Cancelando providers lentos restantes ({len(pending)}).",
                    flush=True,
                )
                break

        if best is not None:
            # Listo: cancelar el resto y salir SIN esperar a los lentos (early exit real)
            for f in list(pending):
                f.cancel()
            pool.shutdown(wait=False, cancel_futures=True)

            tried = []
            for name in chain:
                if name not in results:
                    tried.append({"source": name, "error": "cancelled", "error_class": "cancelled"})
                    continue
                res = results[name]
                tried.append(
                    {
                        "source": name,
                        "id": res.get("resolved_id"),
                        "error": res.get("error"),
                        "error_class": res.get("error_class")
                        or _classify_error(res.get("error")),
                    }
                )
            best["tried"] = tried
            best["lang"] = lang
            print(
                f"[providers] OK lang={lang} provider={best.get('provider')} "
                f"id={best.get('resolved_id')} type={'tv' if is_tv else 'movie'} "
                f"(early-exit, pending={len(pending)})"
            )
            return best
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    # Nadie dio stream
    tried = []
    for name in chain:
        res = results.get(name) or empty_result(name, error="no_stream")
        tried.append(
            {
                "source": name,
                "id": res.get("resolved_id"),
                "error": res.get("error"),
                "error_class": res.get("error_class") or _classify_error(res.get("error")),
            }
        )
    last = results.get(chain[-1]) if chain else None
    out = last or empty_result(chain[0] if chain else "none", error="no_stream")
    out["tried"] = tried
    out["lang"] = lang
    out["error_class"] = out.get("error_class") or _classify_error(out.get("error"))
    print(
        f"[providers] FAIL lang={lang} tried="
        + ",".join(f"{x.get('source')}:{x.get('error')}" for x in tried),
        flush=True,
    )
    return out