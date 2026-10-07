"""Quotes to Scrape: quote cards + (optional, cached) author biography pages."""
import logging
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

import config
from scrapers.base import BaseScraper, text_of

log = logging.getLogger(__name__)


class QuotesScraper(BaseScraper):
    source_name = config.QUOTES_SOURCE_NAME

    def __init__(self, client, base_url=config.QUOTES_BASE_URL, max_pages=None, fetch_authors=True):
        super().__init__(client, base_url, max_pages)
        self.base_url = base_url
        self.fetch_authors = fetch_authors
        self._bio_cache: Dict[str, Optional[str]] = {}

    def guess_page_url(self, page_number):
        return urljoin(self.base_url, f"page/{page_number}/")

    def parse_page(self, soup, page_url) -> Tuple[List[dict], Optional[str]]:
        records = []
        for card in soup.select("div.quote"):
            try:
                text = text_of(card.select_one("span.text"))
                if not text:
                    log.warning("Quote card without text on %s; skipped", page_url)
                    continue
                author_link = card.select_one("a[href^='/author/']")
                records.append(self.new_record(
                    # Quotes have no page of their own: keep the listing page where they were found.
                    source_url=page_url,
                    name_or_title=text,
                    author=text_of(card.select_one("small.author")),
                    tags=[t.get_text(strip=True) for t in card.select("div.tags a.tag")],
                    _author_url=urljoin(page_url, author_link["href"]) if author_link else None,
                ))
            except Exception:
                log.exception("Could not parse a quote on %s", page_url)
        next_link = soup.select_one("li.next a")
        next_url = urljoin(page_url, next_link["href"]) if next_link and next_link.get("href") else None
        return records, next_url

    def _author_bio(self, author_url: Optional[str]) -> Optional[str]:
        if not author_url:
            return None
        if author_url not in self._bio_cache:          # ~50 authors, 100 quotes -> fetch once
            soup = self.client.get_soup(author_url)
            if soup is None:
                self.failed_detail_pages.append(author_url)
                self._bio_cache[author_url] = None
            else:
                self._bio_cache[author_url] = text_of(soup.select_one("div.author-description"))
        return self._bio_cache[author_url]

    def scrape(self) -> List[dict]:
        records = super().scrape()
        for record in records:
            author_url = record.pop("_author_url", None)
            if self.fetch_authors:
                record["description"] = self._author_bio(author_url)
        return records
