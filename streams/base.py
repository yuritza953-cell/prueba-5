"""
Contrato común de providers (estilo TMDB-Embed registry).

Cada provider expone resolve_movie / resolve_tv y devuelve un dict
compatible con el player existente:

  {
    "stream_url": str | None,
    "stream_type": "hls" | "mp4" | None,
    "candidates": [str, ...],
    "ref_url": str,
    "error": str | None,
    "provider": str,          # nombre del provider
    "source": str,            # alias (misma familia)
  }
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


def empty_result(
    provider: str,
    *,
    error: Optional[str] = None,
    ref_url: str = "",
) -> Dict[str, Any]:
    return {
        "stream_url": None,
        "stream_type": None,
        "candidates": [],
        "ref_url": ref_url or "",
        "error": error,
        "provider": provider,
        "source": provider,
    }


def ok_result(
    provider: str,
    stream_url: str,
    *,
    stream_type: Optional[str] = None,
    candidates: Optional[List[str]] = None,
    ref_url: str = "",
    **extra: Any,
) -> Dict[str, Any]:
    cands = list(candidates or [])
    if stream_url and stream_url not in cands:
        cands = [stream_url] + cands
    if stream_type is None:
        low = stream_url.lower()
        stream_type = "mp4" if low.split("?")[0].endswith(".mp4") else "hls"
    out: Dict[str, Any] = {
        "stream_url": stream_url,
        "stream_type": stream_type,
        "candidates": cands,
        "ref_url": ref_url or "",
        "error": None,
        "provider": provider,
        "source": provider,
    }
    out.update(extra)
    return out


def normalize_result(provider: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Adapta el dict de un resolver legacy al contrato común."""
    if not isinstance(data, dict):
        return empty_result(provider, error="invalid_result")
    out = dict(data)
    out.setdefault("provider", provider)
    out.setdefault("source", provider)
    out.setdefault("candidates", [])
    out.setdefault("ref_url", out.get("embed_url") or "")
    url = out.get("stream_url")
    if url and not out.get("stream_type"):
        low = str(url).lower()
        out["stream_type"] = "mp4" if low.split("?")[0].endswith(".mp4") else "hls"
    if url and not out.get("error"):
        out["error"] = None
    return out


@runtime_checkable
class Provider(Protocol):
    name: str
    # idiomas que este provider puede servir
    langs: tuple  # ("es",) | ("en",) | ("es", "en")

    def resolve_movie(self, content_id: str) -> Dict[str, Any]:
        ...

    def resolve_tv(
        self, content_id: str, season: int = 1, episode: int = 1
    ) -> Dict[str, Any]:
        ...