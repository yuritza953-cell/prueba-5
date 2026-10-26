"""
Provider EN: hnembed.cc

Misma familia que VidSrc (vs_src.php → stellar… → m3u8).
Se registra aparte para visibilidad en logs/cadena; el núcleo de
descifrado reutiliza streams.legacy.vidsrc.
"""
from __future__ import annotations

from typing import Any, Dict

from streams.base import normalize_result


class HnEmbedProvider:
    name = "hnembed"
    langs = ("en",)

    def resolve_movie(self, content_id: str) -> Dict[str, Any]:
        from streams.legacy.vidsrc.stream_resolver import resolve_movie

        data = normalize_result(self.name, resolve_movie(content_id))
        data["provider"] = self.name
        data["source"] = self.name
        return data

    def resolve_tv(
        self, content_id: str, season: int = 1, episode: int = 1
    ) -> Dict[str, Any]:
        from streams.legacy.vidsrc.stream_resolver import resolve_tv

        data = normalize_result(self.name, resolve_tv(content_id, season, episode))
        data["provider"] = self.name
        data["source"] = self.name
        return data