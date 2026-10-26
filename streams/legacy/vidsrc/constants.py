"""VidSrc constants."""

BASE_URL = "https://vidsrc.sh"
VS_SRC = BASE_URL.rstrip("/") + "/vs_src.php"
EMBED_MOVIE = BASE_URL.rstrip("/") + "/embed/movie/{content_id}"
EMBED_TV = BASE_URL.rstrip("/") + "/embed/tv/{content_id}/{season}/{episode}"
HTTP_TIMEOUT = 25
