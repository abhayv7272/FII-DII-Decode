"""Low-level NSE access: a browser-like session with cookie priming and retries.

NSE public endpoints reject "cold" requests. The pattern that works:
  1. Hit the homepage (and a relevant referer page) to obtain session cookies.
  2. Reuse the same requests.Session for the API/archive call.
  3. Send realistic browser headers.

This module centralises that so every fetcher behaves consistently.
"""
from __future__ import annotations

import time
import logging
from typing import Optional

import requests

log = logging.getLogger(__name__)

BASE = "https://www.nseindia.com"
ARCHIVES = "https://nsearchives.nseindia.com"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


class NseClient:
    """Reusable NSE HTTP client with cookie priming and retry logic."""

    def __init__(self, timeout: int = 20, max_retries: int = 4, backoff: float = 2.0):
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff = backoff
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self._primed = False

    # ------------------------------------------------------------------ #
    def prime(self, referer: str = BASE + "/option-chain") -> None:
        """Warm up cookies by visiting the homepage + a referer page."""
        try:
            self.session.get(BASE, timeout=self.timeout)
            time.sleep(0.6)
            self.session.get(referer, timeout=self.timeout)
            self.session.headers["Referer"] = referer
            self._primed = True
        except requests.RequestException as exc:  # pragma: no cover - network
            log.warning("Cookie priming failed: %s", exc)

    # ------------------------------------------------------------------ #
    def get(self, url: str, *, as_json: bool = False, referer: Optional[str] = None,
            reprime_on_fail: bool = True):
        """GET a URL with retries. Returns Response, or parsed json if as_json."""
        if not self._primed:
            self.prime()

        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                headers = {}
                if referer:
                    headers["Referer"] = referer
                    headers["Sec-Fetch-Site"] = "same-origin"
                    headers["Sec-Fetch-Mode"] = "cors"
                    headers["X-Requested-With"] = "XMLHttpRequest"
                resp = self.session.get(url, timeout=self.timeout, headers=headers)
                if resp.status_code == 200 and resp.content:
                    return resp.json() if as_json else resp
                log.warning("NSE %s -> HTTP %s (attempt %d)", url, resp.status_code, attempt)
                if resp.status_code in (401, 403) and reprime_on_fail:
                    self._primed = False
                    self.prime()
            except (requests.RequestException, ValueError) as exc:
                last_exc = exc
                log.warning("NSE %s failed (attempt %d): %s", url, attempt, exc)
            time.sleep(self.backoff * attempt)

        raise RuntimeError(f"Failed to fetch {url} after {self.max_retries} attempts: {last_exc}")

    # ------------------------------------------------------------------ #
    def get_text(self, url: str, referer: Optional[str] = None) -> str:
        resp = self.get(url, as_json=False, referer=referer)
        return resp.text

    def get_json(self, url: str, referer: Optional[str] = None) -> dict:
        return self.get(url, as_json=True, referer=referer)
