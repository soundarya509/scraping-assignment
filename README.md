# Multi-Source Web Scraping & Data Consolidation

A Python pipeline that scrapes **Books to Scrape** and **Quotes to Scrape**, maps both into one schema,
cleans and validates records, removes duplicates, and writes a consolidated CSV plus a JSON summary.

```
Books ─┐
       ├─> Scrape ─> Clean ─> Validate ─> Deduplicate ─> Consolidate ─> output/
Quotes ┘
```

## Requirements / setup
* Python **3.9+** (developed and tested on 3.12)
* Dependencies: `requests`, `beautifulsoup4` (scraping); `pymongo` (only used with `--mongo-uri`); `pytest`, `mongomock` (tests only)

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Running
```bash
python main.py                          # full run, both sources (~1,000 book pages: roughly 6-8 min at default rate limit)
python main.py --skip-book-details      # fast run: listing pages only (no category/description for books)
python main.py --max-pages 3 -v         # quick sanity run
python main.py --sources quotes --delay 0.5 --retries 5
python -m pytest -q                     # tests (offline: use HTML fixtures + a fake HTTP client)
```
Options: `--sources`, `--max-pages`, `--skip-book-details`, `--skip-author-details`, `--delay`, `--retries`,
`--timeout`, `--output-dir`, `--log-dir`, `-v`. Defaults live in `config.py`.

## Project structure
```
main.py                 CLI, logging setup
pipeline.py             orchestration + output writing + summary
config.py               URLs, schema, timeouts, retry/rate-limit settings
scrapers/http_client.py retries + exponential backoff, rate limit, robots.txt, charset-safe parsing
scrapers/base.py        shared pagination loop (resilient to failed pages)
scrapers/books_scraper.py, quotes_scraper.py   source-specific selectors only
processing/cleaning.py, validation.py, deduplication.py   pure functions, no network
tests/                  unit + end-to-end tests with fixtures
output/  logs/          generated files
```

## Source exploration (observations)
| | Books to Scrape | Quotes to Scrape |
|---|---|---|
| Listing | `article.product_pod`, 20/page, 50 pages | `div.quote`, 10/page, 10 pages |
| Pagination | `li.next a` with a **relative** href whose base changes (`catalogue/page-2.html` on page 1, `page-3.html` afterwards) | `li.next a` with root-relative href (`/page/2/`) |
| On listing | title (truncated in text, full in `title` attr), price (`£`), rating as a CSS class (`star-rating Three`), availability, detail link | quote text (wrapped in curly quotes), author, tags, author link |
| Only on detail page | **category** (breadcrumb), description | author bio |
| Item URL | one per book | none - quotes share a listing page |

Gotchas handled: `requests` guesses ISO-8859-1 for these pages, which turns `£` into `Â£` - so I parse the raw bytes
(BeautifulSoup reads the meta charset) and `clean_text` also repairs mojibake as a safety net; relative links are resolved with `urljoin` against the *current* page.

## How pagination works
Each scraper's `parse_page()` returns `(records, next_url)`, where `next_url` comes from the page's own "next" link.
`BaseScraper.scrape()` loops until there is no next link. No page URL is hard-coded. Safeguards: loop detection,
a hard cap (`MAX_PAGES_SAFETY`), `--max-pages`. If a page fails (after retries) it is logged and skipped, and the scraper
tries the site's URL pattern for the following page so one bad page does not lose the rest; two consecutive failures stop that source.

## Data model (`output/final_dataset.csv`)
`source, source_url, name_or_title, category, price, currency, rating, author, tags, description, availability, scraped_at`

| Field | Books | Quotes |
|---|---|---|
| name_or_title | book title | quote text (outer quotation marks removed) |
| category | breadcrumb category | empty |
| price / currency | numeric (e.g. 51.77) / `GBP` | empty |
| rating | integer 1-5 | empty |
| author | empty | author name |
| tags | empty | lower-case, `\|`-separated |
| description | product description | author biography |
| availability | e.g. "In stock" | empty |
| source_url | book detail page | listing page the quote was found on (quotes have no own URL) |

Not-applicable fields are **empty (null)** - nothing is invented. `currency` and `availability` are small additions to the suggested schema.

## Cleaning
Whitespace trimmed/collapsed (incl. non-breaking spaces), Unicode NFKC, mojibake repair, placeholder values
(`N/A`, `null`, `-` ...) -> missing, price -> float (currency symbol detected, handles `1,234.50` and `12,5`), rating words/digits -> number,
URLs made absolute with lower-case host and no fragment, tags lower-cased/de-duplicated, wrapping quotes stripped from quotes.
Cleaning never raises on bad values: it records an issue (e.g. `invalid_price:abc`) which validation then rejects.

## Validation
A record is **rejected** (written to `rejected_records.csv` with reasons) if: source unknown; title missing; URL missing/not http(s);
price present but non-numeric or negative; rating outside 1-5; book without price or rating; quote without author.
Reason counts per source are in `summary_report.json`. Category is not required (it is absent by design with `--skip-book-details`).

## Deduplication
Records are duplicates when they share the same **key = (source, normalised title, normalised author)**.
Normalisation: Unicode decomposition with accents removed, case-folding, every non-alphanumeric run replaced by one space, trim.
So `"Example Book Title"`, `" Example Book Title "`, `"EXAMPLE BOOK TITLE"` and `"Example Book, Title!"` match.
For Books (where URL identifies an item) an identical normalised URL also counts. Matching is within a source, and quotes include the author so
the same text by different people is kept.
**Removed, not just flagged**, because the deliverable is one clean dataset - but nothing is lost: every removed row is written to
`duplicates_removed.csv` with `duplicate_of` and `duplicate_reason` (`exact_after_cleaning`, `normalized_match`, `url_match`), and counts per type go in the summary. First occurrence wins.

## Error handling & logging
* Retries with exponential backoff (1s, 2s...) on connection errors, timeouts and HTTP 429/5xx; no retry on 404 and other 4xx.
* Rate limiting (default 0.3 s between requests), identifying User-Agent, robots.txt respected (a missing robots.txt means allowed).
* Missing HTML elements -> `None`; a malformed item is logged and skipped; a page that raises in parsing counts as a failed page.
* A failed detail page keeps the book (category/description empty) and is listed in the summary; a whole-source crash does not stop the other source.
* Logs go to console and `logs/scraper.log` (overwritten each run).

## Output
`output/final_dataset.csv` (UTF-8 with BOM so Excel shows `£`), `output/summary_report.json` (per-source: collected, cleaned, rejected + reasons,
duplicates removed, final, failed pages; totals; duplicate breakdown; execution time), plus `rejected_records.csv` and `duplicates_removed.csv`.

## Optional: MongoDB (bonus)
Off by default. Start MongoDB (e.g. `docker run -d -p 27017:27017 mongo`) and run:
```bash
python main.py --mongo-uri mongodb://localhost:27017 --mongo-db scraping --mongo-collection records
# or: set MONGO_URI=mongodb://localhost:27017   (PowerShell: $env:MONGO_URI="mongodb://localhost:27017")
```
Final (deduplicated) records are **upserted** with `_id` = SHA-1 of the dedup key (source + normalised title + author), so re-running updates
documents (`last_seen_at`) instead of creating duplicates; `first_seen_at` is kept. Each run's summary is stored in `<collection>_runs`.
If MongoDB is unreachable the error is logged and recorded in `summary_report.json` under `storage`; CSV/JSON outputs are still written.
Tests use `mongomock`, so no server is needed to run them.

## Testing
41 offline tests (`python -m pytest -q`): cleaning functions, validation rules, dedup (including the three spec examples), both parsers, pagination with a
failed page, missing elements, retry/backoff and robots.txt via a scripted session, and a full pipeline run. The pipeline was also smoke-tested through the real
`HttpClient` against a local mock server (see `logs/sample_run_LOCAL_MOCK_server.log`, which includes a retried 503).

## Assumptions
* `description` for quotes holds the author's bio (author-related information); it is repeated for each quote by that author.
* Duplicates are decided on title (+author), not price, since the same title with a different price is still the same product listing.
* Rating scale is 1-5 for both sources.

## Known limitations
* No fuzzy matching (typos/near-duplicates); only normalised equality.
* Fetching each book page makes a full run ~1,000 requests; it is sequential (no async/parallelism) to stay polite.
* The guessed-next-page fallback relies on the sites' URL patterns.
* Not incremental: every run re-scrapes everything.

## If this ran in production
Scheduler + incremental scraping (conditional requests / checkpoints), a database with upsert on the dedup key, structured (JSON) logs and
alerting on selector breakage (e.g. a sudden drop in records per page), proxy/concurrency limits, and fixture-based contract tests for the selectors.

## AI usage summary
See `AI_USAGE.md`.
