"""Provider ES opcional: UnlimPlay (activar con ENABLE_UNLIMPLAY=1)."""
from __future__ import annotations

from typing import Any, Dict

from streams.base import normalize_result


class UnlimPlayProvider:
    name = "unlimplay"
    langs = ("es",)

    def resolve_movie(self, content_id: str) -> Dict[str, Any]:
        from streams.legacy.unlimplay.stream_resolver import resolve_movie

        return normalize_result(self.name, resolve_movie(content_id))

    def resolve_tv(
        self, content_id: str, season: int = 1, episode: int = 1
    ) -> Dict[str, Any]:
        from streams.legacy.unlimplay.stream_resolver import resolve_tv

        return normalize_result(self.name, resolve_tv(content_id, season, episode))
