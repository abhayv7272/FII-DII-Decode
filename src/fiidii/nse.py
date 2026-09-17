"""Low-level NSE access: a browser-like session with cookie priming and retries.

NSE public endpoints reject "cold" requests. The pattern that works:
  1. Hit the homepage (and a relevant referer page) to obtain session cookies.
  2. Reuse the same requests.Session for the API/archive call.
  3. Send realistic browser headers.

This module centralises that so every fetcher behaves consistently.
"""

from __future__ import annotations

import logging
import time

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
    # Do not advertise Brotli unless a Brotli decoder is guaranteed installed.
    "Accept-Encoding": "gzip, deflate",
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
            home = self.session.get(BASE, timeout=self.timeout)
            home.raise_for_status()
            time.sleep(0.6)
            page = self.session.get(referer, timeout=self.timeout)
            page.raise_for_status()
            self.session.headers["Referer"] = referer
            self._primed = True
        except requests.RequestException as exc:  # pragma: no cover - network
            self._primed = False
            log.warning("Cookie priming failed: %s", exc)

    # ------------------------------------------------------------------ #
    def get(
        self,
        url: str,
        *,
        as_json: bool = False,
        referer: str | None = None,
        reprime_on_fail: bool = True,
        prime_required: bool = True,
    ):
        """GET a URL with retries. Returns Response, or parsed json if as_json."""
        if prime_required and not self._primed:
            self.prime(referer or BASE + "/option-chain")

        last_exc: Exception | None = None
        last_status: int | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                headers = {}
                if referer:
                    headers["Referer"] = referer
                    headers["Sec-Fetch-Site"] = "same-origin"
                    headers["Sec-Fetch-Mode"] = "cors"
                    headers["X-Requested-With"] = "XMLHttpRequest"
                response = self.session.get(url, timeout=self.timeout, headers=headers)
                last_status = response.status_code
                if response.status_code == 200 and response.content:
                    return response.json() if as_json else response
                log.warning(
                    "NSE %s -> HTTP %s (attempt %d)",
                    url,
                    response.status_code,
                    attempt,
                )
                # Missing dated archive files and permanent client errors should
                # fall through to the next source immediately, not burn all retries.
                if response.status_code == 404 or (
                    400 <= response.status_code < 500
                    and response.status_code not in (401, 403, 429)
                ):
                    raise RuntimeError(
                        f"NSE returned HTTP {response.status_code} for {url}"
                    )
                if response.status_code in (401, 403) and reprime_on_fail:
                    self._primed = False
                    self.prime(referer or BASE + "/option-chain")
            except RuntimeError:
                raise
            except (requests.RequestException, ValueError) as exc:
                last_exc = exc
                log.warning("NSE %s failed (attempt %d): %s", url, attempt, exc)
            if attempt < self.max_retries:
                time.sleep(self.backoff * attempt)

        detail = f"HTTP {last_status}" if last_status else str(last_exc)
        raise RuntimeError(
            f"Failed to fetch {url} after {self.max_retries} attempts: {detail}"
        )

    # ------------------------------------------------------------------ #
    def get_text(
        self,
        url: str,
        referer: str | None = None,
        *,
        prime_required: bool = True,
    ) -> str:
        response = self.get(
            url,
            as_json=False,
            referer=referer,
            prime_required=prime_required,
            reprime_on_fail=prime_required,
        )
        return response.text

    def get_json(self, url: str, referer: str | None = None):
        return self.get(url, as_json=True, referer=referer)
