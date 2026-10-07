"""HTTP layer: retries with exponential backoff, rate limiting, robots.txt check."""
import logging
import time
from typing import Optional
from urllib import robotparser
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup

import config

log = logging.getLogger(__name__)


class HttpClient:
    def __init__(self, timeout=config.REQUEST_TIMEOUT, max_retries=config.MAX_RETRIES,
                 backoff=config.BACKOFF_FACTOR, delay=config.REQUEST_DELAY,
                 user_agent=config.USER_AGENT, respect_robots=True, session=None):
        self.timeout = timeout
        self.max_retries = max(1, max_retries)
        self.backoff = backoff
        self.delay = delay
        self.respect_robots = respect_robots
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self._last_request = 0.0
        self._robots = {}  # host -> RobotFileParser | None (None = allow all)

    # -- politeness ---------------------------------------------------------
    def _throttle(self):
        wait = self.delay - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    def allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        parts = urlsplit(url)
        host = f"{parts.scheme}://{parts.netloc}"
        if host not in self._robots:
            self._robots[host] = self._load_robots(host)
        parser = self._robots[host]
        return True if parser is None else parser.can_fetch(self.session.headers["User-Agent"], url)

    def _load_robots(self, host: str):
        try:
            self._throttle()
            resp = self.session.get(f"{host}/robots.txt", timeout=self.timeout)
            if resp.status_code != 200:      # no robots.txt (404) => nothing is disallowed
                log.info("No usable robots.txt at %s (HTTP %s); allowing", host, resp.status_code)
                return None
            parser = robotparser.RobotFileParser()
            parser.parse(resp.text.splitlines())
            return parser
        except requests.RequestException as exc:
            log.warning("Could not read robots.txt at %s (%s); allowing", host, exc)
            return None

    # -- fetching -----------------------------------------------------------
    def get(self, url: str) -> Optional[requests.Response]:
        """GET with retries. Returns None when the page could not be fetched."""
        if not self.allowed(url):
            log.warning("Blocked by robots.txt, skipping: %s", url)
            return None
        for attempt in range(1, self.max_retries + 1):
            self._throttle()
            try:
                resp = self.session.get(url, timeout=self.timeout)
            except (requests.ConnectionError, requests.Timeout) as exc:
                log.warning("Attempt %d/%d failed for %s: %s", attempt, self.max_retries, url, exc)
            except requests.RequestException as exc:      # invalid URL etc. - not retryable
                log.error("Non-retryable error for %s: %s", url, exc)
                return None
            else:
                if resp.status_code == 200:
                    return resp
                if resp.status_code in config.RETRY_STATUS_CODES:
                    log.warning("Attempt %d/%d: HTTP %s for %s", attempt, self.max_retries,
                                resp.status_code, url)
                else:
                    log.error("HTTP %s for %s (not retrying)", resp.status_code, url)
                    return None
            if attempt < self.max_retries:
                time.sleep(self.backoff * 2 ** (attempt - 1))
        log.error("Giving up on %s after %d attempts", url, self.max_retries)
        return None

    def get_soup(self, url: str) -> Optional[BeautifulSoup]:
        resp = self.get(url)
        if resp is None:
            return None
        # Parse the raw bytes so BeautifulSoup honours the page's own charset
        # (requests would guess ISO-8859-1 and produce "Â£" mojibake).
        return BeautifulSoup(resp.content, "html.parser")
