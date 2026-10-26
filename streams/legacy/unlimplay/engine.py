from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests

from core.logger import log
from config import settings

from .constants import (
    EMBED_MOVIE,
    EMBED_TV,
    HTTP_TIMEOUT,
    MAX_SEARCH_RESULTS,
    TMDB_BASE,
    TMDB_IMAGE_W500,
)


@dataclass
class MovieItem:
    tmdb_id: int
    title: str
    year: Optional[str] = None
    overview: Optional[str] = None
    poster_url: Optional[str] = None
    director: Optional[str] = None
    imdb_id: Optional[str] = None
    vote_average: Optional[float] = None
    runtime: Optional[int] = None


@dataclass
class SeasonInfo:
    season_number: int
    name: str
    episode_count: int
    poster_url: Optional[str] = None


@dataclass
class SeriesItem:
    tmdb_id: int
    title: str
    year: Optional[str] = None
    overview: Optional[str] = None
    poster_url: Optional[str] = None
    imdb_id: Optional[str] = None
    vote_average: Optional[float] = None
    number_of_seasons: int = 0
    seasons: List[SeasonInfo] = field(default_factory=list)


class UnlimPlayEngine:
    """Motor UnlimPlay + TMDB (búsqueda, detalles, embeds)."""

    def __init__(self, tmdb_api_key: Optional[str] = None):
        self.tmdb_api_key = tmdb_api_key or getattr(settings, "TMDB_API_KEY", None)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json,text/html,*/*;q=0.8",
                "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            }
        )

    @property
    def has_tmdb(self) -> bool:
        return bool(self.tmdb_api_key and str(self.tmdb_api_key).strip())

    @staticmethod
    def _tmdb_lang(lang: Optional[str] = None) -> str:
        v = (lang or "es").strip().lower()
        if v.startswith("en"):
            return "en-US"
        return "es-ES"

    def _tmdb_get(self, path: str, params: Optional[Dict] = None) -> Dict:
        if not self.has_tmdb:
            raise ValueError(
                "TMDB API key no configurada. Añade TMDB_API_KEY en el .env "
                "(gratis en https://www.themoviedb.org/settings/api)"
            )
        url = f"{TMDB_BASE}{path}"
        p: Dict[str, Any] = {"api_key": self.tmdb_api_key, "language": "es-ES"}
        if params:
            p.update(params)
        # params puede sobreescribir language (en-US / es-ES)

        try:
            r = self.session.get(url, params=p, timeout=HTTP_TIMEOUT)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.warning(f"TMDB error {path}: {e}")
            raise

    def _poster(self, path: Optional[str]) -> Optional[str]:
        if not path:
            return None
        return f"{TMDB_IMAGE_W500}{path}"

    def search_movies(self, query: str, lang: str = "es") -> List[MovieItem]:
        data = self._tmdb_get("/search/movie", {"query": query, "page": 1, "language": self._tmdb_lang(lang)})
        results = data.get("results", [])[:MAX_SEARCH_RESULTS]
        items: List[MovieItem] = []
        for r in results:
            year = None
            if r.get("release_date"):
                year = r["release_date"][:4]
            items.append(
                MovieItem(
                    tmdb_id=r["id"],
                    title=r.get("title") or r.get("original_title") or "Sin título",
                    year=year,
                    overview=(r.get("overview") or "")[:300] or None,
                    poster_url=self._poster(r.get("poster_path")),
                    vote_average=r.get("vote_average"),
                )
            )
        return items

    def search_tv(self, query: str, lang: str = "es") -> List[SeriesItem]:
        data = self._tmdb_get("/search/tv", {"query": query, "page": 1, "language": self._tmdb_lang(lang)})
        results = data.get("results", [])[:MAX_SEARCH_RESULTS]
        items: List[SeriesItem] = []
        for r in results:
            year = None
            if r.get("first_air_date"):
                year = r["first_air_date"][:4]
            items.append(
                SeriesItem(
                    tmdb_id=r["id"],
                    title=r.get("name") or r.get("original_name") or "Sin título",
                    year=year,
                    overview=(r.get("overview") or "")[:300] or None,
                    poster_url=self._poster(r.get("poster_path")),
                    vote_average=r.get("vote_average"),
                )
            )
        return items

    def enrich_movie(self, item: MovieItem, lang: str = "es") -> MovieItem:
        try:
            data = self._tmdb_get(
                f"/movie/{item.tmdb_id}",
                {"append_to_response": "credits", "language": self._tmdb_lang(lang)},
            )
        except Exception:
            return item

        if data.get("imdb_id"):
            item.imdb_id = data["imdb_id"]
        if data.get("runtime"):
            item.runtime = data["runtime"]
        if data.get("overview") and not item.overview:
            item.overview = data["overview"][:300]
        if data.get("poster_path") and not item.poster_url:
            item.poster_url = self._poster(data["poster_path"])
        if data.get("release_date") and not item.year:
            item.year = data["release_date"][:4]
        if data.get("title"):
            item.title = data["title"]

        credits = data.get("credits") or {}
        directors = [
            c["name"]
            for c in credits.get("crew", [])
            if c.get("job") == "Director"
        ]
        if directors:
            item.director = ", ".join(directors[:3])
        return item

    def enrich_series(self, item: SeriesItem, lang: str = "es") -> SeriesItem:
        try:
            data = self._tmdb_get(
                f"/tv/{item.tmdb_id}",
                {"append_to_response": "external_ids", "language": self._tmdb_lang(lang)},
            )
        except Exception:
            return item

        if data.get("name"):
            item.title = data["name"]
        if data.get("overview") and not item.overview:
            item.overview = data["overview"][:300]
        if data.get("poster_path") and not item.poster_url:
            item.poster_url = self._poster(data["poster_path"])
        if data.get("first_air_date") and not item.year:
            item.year = data["first_air_date"][:4]
        item.number_of_seasons = data.get("number_of_seasons") or 0

        ext = data.get("external_ids") or {}
        if ext.get("imdb_id"):
            item.imdb_id = ext["imdb_id"]

        seasons: List[SeasonInfo] = []
        for s in data.get("seasons") or []:
            sn = s.get("season_number")
            if sn is None or sn < 1:
                continue
            seasons.append(
                SeasonInfo(
                    season_number=int(sn),
                    name=s.get("name") or (f"Season {sn}" if (lang or "es").startswith("en") else f"Temporada {sn}"),
                    episode_count=int(s.get("episode_count") or 0),
                    poster_url=self._poster(s.get("poster_path")),
                )
            )
        item.seasons = seasons
        return item

    def movie_embed_url(self, tmdb_id: int, imdb_id: Optional[str] = None) -> str:
        content_id = imdb_id if imdb_id else str(tmdb_id)
        return EMBED_MOVIE.format(content_id=content_id)

    def tv_embed_url(
        self,
        tmdb_id: int,
        season: int,
        episode: int,
        imdb_id: Optional[str] = None,
    ) -> str:
        content_id = imdb_id if imdb_id else str(tmdb_id)
        return EMBED_TV.format(content_id=content_id, season=season, episode=episode)

    def generate_iframe(self, embed_url: str, width: str = "100%", height: str = "500") -> str:
        return (
            f'<iframe src="{embed_url}" width="{width}" height="{height}" '
            f'frameborder="0" allowfullscreen scrolling="no"></iframe>'
        )

    async def search_movies_async(self, query: str, lang: str = "es") -> List[MovieItem]:
        return await asyncio.to_thread(self.search_movies, query, lang)

    async def search_tv_async(self, query: str, lang: str = "es") -> List[SeriesItem]:
        return await asyncio.to_thread(self.search_tv, query, lang)

    async def enrich_movie_async(self, item: MovieItem, lang: str = "es") -> MovieItem:
        return await asyncio.to_thread(self.enrich_movie, item, lang)

    async def enrich_series_async(self, item: SeriesItem, lang: str = "es") -> SeriesItem:
        return await asyncio.to_thread(self.enrich_series, item, lang)