"""Books to Scrape: listing pages + (optional) detail pages for category/description."""
import logging
from typing import List, Optional, Tuple
from urllib.parse import urljoin

import config
from scrapers.base import BaseScraper, text_of

log = logging.getLogger(__name__)


class BooksScraper(BaseScraper):
    source_name = config.BOOKS_SOURCE_NAME

    def __init__(self, client, base_url=config.BOOKS_BASE_URL, max_pages=None, fetch_details=True):
        super().__init__(client, base_url, max_pages)
        self.base_url = base_url
        self.fetch_details = fetch_details

    def guess_page_url(self, page_number):
        return urljoin(self.base_url, f"catalogue/page-{page_number}.html")

    def parse_page(self, soup, page_url) -> Tuple[List[dict], Optional[str]]:
        records = []
        for card in soup.select("article.product_pod"):
            try:
                link = card.select_one("h3 a")
                if link is None:
                    log.warning("Book card without title link on %s; skipped", page_url)
                    continue
                rating_el = card.select_one("p.star-rating")
                records.append(self.new_record(
                    source_url=urljoin(page_url, link.get("href", "")),
                    name_or_title=link.get("title") or text_of(link),
                    price=text_of(card.select_one("p.price_color")),
                    # raw value is e.g. "star-rating Three"; cleaning converts it to 3
                    rating=" ".join(rating_el.get("class", [])) if rating_el is not None else None,
                    availability=text_of(card.select_one("p.availability")),
                ))
            except Exception:
                log.exception("Could not parse a book card on %s", page_url)
        next_link = soup.select_one("li.next a")
        next_url = urljoin(page_url, next_link["href"]) if next_link and next_link.get("href") else None
        return records, next_url

    def parse_detail(self, soup) -> Tuple[Optional[str], Optional[str]]:
        crumbs = soup.select("ul.breadcrumb li a")          # Home > Books > <Category>
        category = text_of(crumbs[2]) if len(crumbs) >= 3 else None
        desc_header = soup.select_one("#product_description")
        description = text_of(desc_header.find_next_sibling("p")) if desc_header is not None else None
        return category, description

    def scrape(self) -> List[dict]:
        records = super().scrape()
        if self.fetch_details:
            for index, record in enumerate(records, 1):
                url = record["source_url"]
                soup = self.client.get_soup(url)
                if soup is None:
                    self.failed_detail_pages.append(url)
                    continue
                try:
                    record["category"], record["description"] = self.parse_detail(soup)
                except Exception:
                    log.exception("Could not parse detail page %s", url)
                    self.failed_detail_pages.append(url)
                if index % 100 == 0:
                    log.info("[%s] detail pages: %d/%d", self.source_name, index, len(records))
        return records
