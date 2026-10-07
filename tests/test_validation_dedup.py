import config
from processing.cleaning import clean_record
from processing.deduplication import deduplicate, normalize_for_matching
from processing.validation import validate_record

B, Q = config.BOOKS_SOURCE_NAME, config.QUOTES_SOURCE_NAME


def book(title="T", url="https://books.toscrape.com/a.html", **kw):
    raw = {"source": B, "source_url": url, "name_or_title": title, "price": "£10.00", "rating": "star-rating Two"}
    raw.update(kw)
    return clean_record(raw)


def test_valid_book_and_quote():
    assert validate_record(book()) == []
    q = clean_record({"source": Q, "source_url": "https://quotes.toscrape.com/", "name_or_title": "“x”", "author": "A"})
    assert validate_record(q) == []


def test_validation_errors():
    codes = lambda r: {e.split(":")[0] for e in validate_record(r)}
    assert "missing_name_or_title" in codes(book(title="  "))
    assert "rating_out_of_range" in codes(book(rating="9"))
    assert "invalid_price" in codes(book(price="abc"))
    assert "missing_price" in codes(book(price=None))
    assert "unknown_source" in codes(book(source="Nope"))
    assert "invalid_url" in codes(book(url="ftp://x"))
    assert "missing_source_url" in codes(book(url=None))
    assert "missing_author" in codes(clean_record({"source": Q, "source_url": "https://q.com/", "name_or_title": "x"}))


def test_normalize_for_matching():
    variants = ["Example Book Title", " Example Book Title ", "EXAMPLE BOOK TITLE", "Example  Book, Title!", "Éxample Book Title"]
    assert len({normalize_for_matching(v) for v in variants}) == 1


def test_dedup_spec_examples_and_reasons():
    recs = [book("Example Book Title", "https://books.toscrape.com/1.html"),
            book(" EXAMPLE BOOK TITLE ", "https://books.toscrape.com/2.html"),
            book("Example Book Title", "https://books.toscrape.com/3.html"),
            book("Other", "https://books.toscrape.com/4.html"),
            book("Different Title", "https://books.toscrape.com/4.html")]
    unique, removed, stats = deduplicate(recs)
    assert [r["source_url"][-7:] for r in unique] == ["/1.html", "/4.html"]
    assert stats["normalized_match"] == 1 and stats["exact_after_cleaning"] == 1 and stats["url_match"] == 1
    assert all(r["duplicate_of"] for r in removed)


def test_same_text_different_author_or_source_is_not_duplicate():
    mk = lambda a, s=Q: clean_record({"source": s, "source_url": "https://q.com/", "name_or_title": "Same", "author": a})
    unique, removed, _ = deduplicate([mk("A"), mk("B"), mk("A", B)])
    assert len(unique) == 3 and not removed
