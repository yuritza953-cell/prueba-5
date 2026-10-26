from __future__ import annotations

BASE_URL = "https://unlimplay.com"

EMBED_MOVIE = f"{BASE_URL}/f/embed/movie/{{content_id}}"
EMBED_TV = f"{BASE_URL}/f/embed/tv/{{content_id}}/{{season}}/{{episode}}"

TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_W500 = "https://image.tmdb.org/t/p/w500"
TMDB_IMAGE_ORIGINAL = "https://image.tmdb.org/t/p/original"

HTTP_TIMEOUT = 25
EMBED_COLOR = 0x5865F2
MAX_SEARCH_RESULTS = 20
MAX_SELECT_OPTIONS = 25