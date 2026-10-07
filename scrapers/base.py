"""Shared pagination loop. Subclasses only supply page parsing + a URL guess."""
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import config

log = logging.getLogger(__name__)


def text_of(element) -> Optional[str]:
    return element.get_text(" ", strip=True) if element is not None else None


class BaseScraper(ABC):
    source_name = ""

    def __init__(self, client, start_url: str, max_pages: Optional[int] = None):
        self.client = client
        self.start_url = start_url
        self.max_pages = max_pages
        self.failed_pages: List[str] = []
        self.failed_detail_pages: List[str] = []
        self.pages_scraped = 0

    # -- to be implemented by sources --------------------------------------
    @abstractmethod
    def parse_page(self, soup, page_url: str) -> Tuple[List[dict], Optional[str]]:
        """Return (raw records on this page, absolute URL of next page or None)."""

    def guess_page_url(self, page_number: int) -> Optional[str]:
        """URL pattern fallback used only when a page fails and its 'next' link is unknown."""
        return None

    # -- helpers -------------------------------------------------------------
    def new_record(self, **fields) -> dict:
        record = {name: None for name in config.SCHEMA_FIELDS}
        record.update(source=self.source_name,
                      scraped_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        record.update(fields)
        return record

    # -- pagination ----------------------------------------------------------
    def scrape(self) -> List[dict]:
        records: List[dict] = []
        url: Optional[str] = self.start_url
        page, consecutive_failures, seen = 1, 0, set()
        while url and page <= config.MAX_PAGES_SAFETY and (self.max_pages is None or page <= self.max_pages):
            if url in seen:
                log.warning("Pagination loop detected at %s; stopping", url)
                break
            seen.add(url)
            log.info("[%s] page %d: %s", self.source_name, page, url)
            items, next_url, ok = [], None, False
            soup = self.client.get_soup(url)
            if soup is not None:
                try:
                    items, next_url = self.parse_page(soup, url)
                    ok = True
                except Exception:  # one bad page must not kill the run
                    log.exception("[%s] parse error on %s", self.source_name, url)
            if ok:
                consecutive_failures = 0
                self.pages_scraped += 1
                records.extend(items)
                log.info("[%s] page %d: %d records", self.source_name, page, len(items))
            else:
                self.failed_pages.append(url)
                consecutive_failures += 1
                if consecutive_failures >= 2:
                    log.error("[%s] two consecutive page failures; stopping pagination", self.source_name)
                    break
                next_url = self.guess_page_url(page + 1)
                log.warning("[%s] page failed; trying guessed next URL %s", self.source_name, next_url)
            url, page = next_url, page + 1
        log.info("[%s] pagination finished: %d pages ok, %d failed, %d raw records",
                 self.source_name, self.pages_scraped, len(self.failed_pages), len(records))
        return records
