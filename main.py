"""CLI entry point:  python main.py --help"""
import argparse
import logging
import os
import sys
from pathlib import Path

import config
from pipeline import run_pipeline
from scrapers.books_scraper import BooksScraper
from scrapers.http_client import HttpClient
from scrapers.quotes_scraper import QuotesScraper


def setup_logging(log_dir: Path, verbose: bool) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    for handler in (logging.FileHandler(log_dir / "scraper.log", mode="w", encoding="utf-8"),
                    logging.StreamHandler()):
        handler.setFormatter(fmt)
        root.addHandler(handler)


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Multi-source scraping & consolidation pipeline")
    p.add_argument("--sources", nargs="+", choices=["books", "quotes"], default=["books", "quotes"])
    p.add_argument("--max-pages", type=int, default=None, help="limit listing pages per source (default: all)")
    p.add_argument("--skip-book-details", action="store_true", help="don't open each book page (no category/description; much faster)")
    p.add_argument("--skip-author-details", action="store_true", help="don't fetch author bios")
    p.add_argument("--delay", type=float, default=config.REQUEST_DELAY, help="seconds between requests")
    p.add_argument("--retries", type=int, default=config.MAX_RETRIES)
    p.add_argument("--timeout", type=float, default=config.REQUEST_TIMEOUT)
    p.add_argument("--mongo-uri", default=os.environ.get("MONGO_URI"),
                   help="optional MongoDB URI, e.g. mongodb://localhost:27017 (or set MONGO_URI)")
    p.add_argument("--mongo-db", default="scraping")
    p.add_argument("--mongo-collection", default="records")
    p.add_argument("--output-dir", default="output")
    p.add_argument("--log-dir", default="logs")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    setup_logging(Path(args.log_dir), args.verbose)
    client = HttpClient(timeout=args.timeout, max_retries=args.retries, delay=args.delay)
    scrapers = []
    if "books" in args.sources:
        scrapers.append(BooksScraper(client, max_pages=args.max_pages, fetch_details=not args.skip_book_details))
    if "quotes" in args.sources:
        scrapers.append(QuotesScraper(client, max_pages=args.max_pages, fetch_authors=not args.skip_author_details))
    store = None
    if args.mongo_uri:
        from storage import MongoStore
        store = MongoStore(args.mongo_uri, args.mongo_db, args.mongo_collection)
    summary = run_pipeline(scrapers, args.output_dir, store=store)
    return 0 if summary["totals"]["final"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
