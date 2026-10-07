"""Central configuration (defaults; most can be overridden from the CLI)."""

BOOKS_SOURCE_NAME = "Books to Scrape"
QUOTES_SOURCE_NAME = "Quotes to Scrape"
BOOKS_BASE_URL = "https://books.toscrape.com/"
QUOTES_BASE_URL = "https://quotes.toscrape.com/"

USER_AGENT = "interview-scraping-assignment/1.0 (educational; respects robots.txt)"
REQUEST_TIMEOUT = 15          # seconds
MAX_RETRIES = 3               # attempts per URL
BACKOFF_FACTOR = 1.0          # sleep = BACKOFF_FACTOR * 2**(attempt-1)
REQUEST_DELAY = 0.3           # minimum seconds between requests (rate limit)
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_PAGES_SAFETY = 500        # hard stop so a pagination bug can never loop forever

# Standardised schema (column order of final_dataset.csv)
SCHEMA_FIELDS = [
    "source", "source_url", "name_or_title", "category", "price", "currency",
    "rating", "author", "tags", "description", "availability", "scraped_at",
]
KNOWN_SOURCES = {BOOKS_SOURCE_NAME, QUOTES_SOURCE_NAME}
# Sources whose source_url identifies ONE item (quotes share their listing-page URL)
ITEM_LEVEL_URL_SOURCES = {BOOKS_SOURCE_NAME}
RATING_MIN, RATING_MAX = 1, 5
