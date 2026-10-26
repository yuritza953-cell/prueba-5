"""
Resolución de streams para CineBusca.

Uso principal:
    from streams import resolve_stream

    result = resolve_stream(
        media="movie",          # movie | tv
        tmdb_id="12345",
        lang="es",              # es | en
        season=1,               # solo tv
        episode=1,              # solo tv
        imdb_id="tt1234567",    # opcional, algunos providers lo prefieren
    )
"""
from __future__ import annotations

from streams.service import resolve_stream

__all__ = ["resolve_stream"]
