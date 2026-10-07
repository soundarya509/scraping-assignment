import csv, json
import requests
import config
from pipeline import run_pipeline
from scrapers.books_scraper import BooksScraper
from scrapers.http_client import HttpClient
from scrapers.quotes_scraper import QuotesScraper
from tests.fakes import *


def test_end_to_end(tmp_path):
    pages = {
        BOOKS: books_page([book_card("Example Book Title", "a_1/index.html"),
                           book_card(" EXAMPLE BOOK TITLE ", "b_2/index.html"),
                           book_card("Bad Price", "c_3/index.html", price="free"),
                           book_card("Good", "d_4/index.html", price="Â£20.50", rating="One")]),
        QUOTES: quotes_page([quote_card("Hello", "Ann", ["a"]), quote_card("hello!", "ann", ["A"]), quote_card("Other", "", ["b"])]),
    }
    client = FakeClient(pages)
    summary = run_pipeline([BooksScraper(client, fetch_details=False), QuotesScraper(client, fetch_authors=False)], tmp_path)
    b, q = summary["sources"][config.BOOKS_SOURCE_NAME], summary["sources"][config.QUOTES_SOURCE_NAME]
    assert (b["collected"], b["rejected_validation"], b["duplicates_removed"], b["final"]) == (4, 1, 1, 2)
    assert (q["collected"], q["rejected_validation"], q["duplicates_removed"], q["final"]) == (3, 1, 1, 1)
    assert summary["totals"]["final"] == 3 and b["rejection_reasons"] == {"invalid_price": 1}
    rows = list(csv.DictReader(open(tmp_path / "final_dataset.csv", encoding="utf-8-sig")))
    assert list(rows[0].keys()) == config.SCHEMA_FIELDS and len(rows) == 3
    good = next(r for r in rows if r["name_or_title"] == "Good")
    assert good["price"] == "20.5" and good["rating"] == "1" and good["currency"] == "GBP"
    assert json.load(open(tmp_path / "summary_report.json"))["totals"]["duplicates_removed"] == 2
    assert (tmp_path / "rejected_records.csv").exists() and (tmp_path / "duplicates_removed.csv").exists()


def test_one_source_crashing_does_not_stop_the_other(tmp_path):
    class Boom(BooksScraper):
        def scrape(self):
            raise RuntimeError("boom")
    client = FakeClient({QUOTES: quotes_page([quote_card("Hi", "Ann", [])])})
    s = run_pipeline([Boom(client), QuotesScraper(client, fetch_authors=False)], tmp_path)
    assert s["sources"][config.BOOKS_SOURCE_NAME]["fatal_error"] and s["totals"]["final"] == 1


class Resp:
    def __init__(self, code, content=b"<html></html>", text=""):
        self.status_code, self.content, self.text = code, content, text


class ScriptedSession:
    def __init__(self, outcomes):
        self.outcomes, self.calls, self.headers = list(outcomes), 0, {}

    def get(self, url, timeout=None):
        if url.endswith("robots.txt"):
            return Resp(404)
        self.calls += 1
        out = self.outcomes.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


def make_client(outcomes, retries=3):
    return HttpClient(session=ScriptedSession(outcomes), max_retries=retries, backoff=0, delay=0)


def test_http_retries_then_succeeds():
    c = make_client([requests.Timeout(), Resp(503), Resp(200)])
    assert c.get("https://x.com/a") is not None and c.session.calls == 3


def test_http_gives_up_and_does_not_retry_404():
    c = make_client([requests.ConnectionError()] * 3)
    assert c.get("https://x.com/a") is None and c.session.calls == 3
    c = make_client([Resp(404)])
    assert c.get("https://x.com/a") is None and c.session.calls == 1


def test_robots_disallow_is_respected():
    class S(ScriptedSession):
        def get(self, url, timeout=None):
            return Resp(200, text="User-agent: *\nDisallow: /private") if url.endswith("robots.txt") else super().get(url, timeout)
    c = HttpClient(session=S([Resp(200)]), delay=0, backoff=0)
    assert c.get("https://x.com/private/a") is None and c.get("https://x.com/public") is not None
