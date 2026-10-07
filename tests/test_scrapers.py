import config
from scrapers.books_scraper import BooksScraper
from scrapers.quotes_scraper import QuotesScraper
from tests.fakes import *

P1, P2, P3 = BOOKS, BOOKS + "catalogue/page-2.html", BOOKS + "catalogue/page-3.html"


def books_site(**overrides):
    pages = {
        P1: books_page([book_card("Book A", "catalogue/a_1/index.html"), book_card("Book B", "catalogue/b_2/index.html", price="Â£9.99")],
                       "catalogue/page-2.html"),
        P2: books_page([book_card("Book C", "c_3/index.html", rating="Five")], "page-3.html"),
        P3: books_page([book_card("Book D", "d_4/index.html")]),
        BOOKS + "catalogue/a_1/index.html": book_detail("Poetry", "Desc A"),
        BOOKS + "catalogue/b_2/index.html": book_detail("Travel", None),
        BOOKS + "catalogue/c_3/index.html": book_detail("Fiction", "Desc C"),
        BOOKS + "catalogue/d_4/index.html": book_detail("Mystery", "Desc D"),
    }
    pages.update(overrides)
    return FakeClient(pages)


def test_books_follow_pagination_until_no_next_link():
    s = BooksScraper(books_site())
    recs = s.scrape()
    assert [r["name_or_title"] for r in recs] == ["Book A", "Book B", "Book C", "Book D"]
    assert s.pages_scraped == 3 and not s.failed_pages
    assert recs[0]["source_url"] == BOOKS + "catalogue/a_1/index.html"   # relative URLs resolved per page
    assert recs[0]["category"] == "Poetry" and recs[1]["description"] is None   # missing description -> None
    assert recs[2]["rating"] == "star-rating Five"


def test_books_max_pages_and_skip_details():
    s = BooksScraper(books_site(), max_pages=1, fetch_details=False)
    recs = s.scrape()
    assert len(recs) == 2 and recs[0]["category"] is None


def test_books_failed_page_is_skipped_and_scraping_continues():
    s = BooksScraper(books_site(**{P2: None}), fetch_details=False)
    recs = s.scrape()
    assert [r["name_or_title"] for r in recs] == ["Book A", "Book B", "Book D"]   # page 3 reached via URL guess
    assert s.failed_pages == [P2]


def test_books_missing_elements_do_not_crash():
    html = books_page(["<li><article class='product_pod'><h3><a href='x_1/index.html'>NoTitleAttr</a></h3></article></li>",
                       "<li><article class='product_pod'><p>broken</p></article></li>"])
    recs = BooksScraper(FakeClient({P1: html}), fetch_details=False).scrape()
    assert len(recs) == 1 and recs[0]["name_or_title"] == "NoTitleAttr" and recs[0]["price"] is None and recs[0]["rating"] is None


def test_quotes_pagination_tags_and_cached_author_fetch():
    pages = {QUOTES: quotes_page([quote_card("Q1", "Ann", ["love", "life"]), quote_card("Q2", "Ann", [])], "/page/2/"),
             QUOTES + "page/2/": quotes_page([quote_card("Q3", "Bob", ["x"], "/author/Bob")]),
             QUOTES + "author/Some-Author": author_page("Ann bio"), QUOTES + "author/Bob": author_page("Bob bio")}
    client = FakeClient(pages)
    s = QuotesScraper(client)
    recs = s.scrape()
    assert [r["author"] for r in recs] == ["Ann", "Ann", "Bob"]
    assert recs[0]["tags"] == ["love", "life"] and recs[1]["tags"] == []
    assert recs[0]["name_or_title"] == "“Q1”" and recs[2]["description"] == "Bob bio"
    assert recs[1]["source_url"] == QUOTES and recs[2]["source_url"] == QUOTES + "page/2/"
    assert client.requested.count(QUOTES + "author/Some-Author") == 1      # cached
    assert "_author_url" not in recs[0]


def test_two_consecutive_failures_stop_pagination():
    s = QuotesScraper(FakeClient({}), fetch_authors=False)
    assert s.scrape() == [] and len(s.failed_pages) == 2
