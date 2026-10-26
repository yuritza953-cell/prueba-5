"""Provider EN: VidSrc."""
from __future__ import annotations

from typing import Any, Dict

from streams.base import normalize_result


class VidSrcProvider:
    name = "vidsrc"
    langs = ("en",)

    def resolve_movie(self, content_id: str) -> Dict[str, Any]:
        from streams.legacy.vidsrc.stream_resolver import resolve_movie

        return normalize_result(self.name, resolve_movie(content_id))

    def resolve_tv(
        self, content_id: str, season: int = 1, episode: int = 1
    ) -> Dict[str, Any]:
        from streams.legacy.vidsrc.stream_resolver import resolve_tv

        return normalize_result(self.name, resolve_tv(content_id, season, episode))
