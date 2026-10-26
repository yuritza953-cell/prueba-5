"""
Cliente HTTP compartido para providers.

- User-Agent Chrome real (no Python-urllib)
- Accept-Language es-419 (contenido latino)
- Prefer curl_cffi con impersonate; fallback requests
"""
from __future__ import annotations

from typing import Any, Dict, Optional

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

DEFAULT_HEADERS: Dict[str, str] = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-419,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
}


def browser_headers(**extra: str) -> Dict[str, str]:
    h = dict(DEFAULT_HEADERS)
    h.update({k: v for k, v in extra.items() if v is not None})
    return h


def get(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 20,
    allow_redirects: bool = True,
    verify: bool = False,
    cookies: Any = None,
) -> Any:
    """GET con UA Chrome. Devuelve response (curl_cffi o requests)."""
    hdrs = browser_headers(**(headers or {}))
    try:
        from curl_cffi import requests as creq

        return creq.get(
            url,
            headers=hdrs,
            timeout=timeout,
            allow_redirects=allow_redirects,
            verify=verify,
            cookies=cookies,
            impersonate="chrome131",
        )
    except Exception:
        import requests
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        return requests.get(
            url,
            headers=hdrs,
            timeout=timeout,
            allow_redirects=allow_redirects,
            verify=verify,
            cookies=cookies,
        )


def head(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 12,
    allow_redirects: bool = True,
) -> Any:
    hdrs = browser_headers(**(headers or {}))
    try:
        from curl_cffi import requests as creq

        return creq.head(
            url,
            headers=hdrs,
            timeout=timeout,
            allow_redirects=allow_redirects,
            verify=False,
            impersonate="chrome131",
        )
    except Exception:
        import requests
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        return requests.head(
            url,
            headers=hdrs,
            timeout=timeout,
            allow_redirects=allow_redirects,
            verify=False,
        )
