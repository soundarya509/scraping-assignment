import pytest
from processing import cleaning as c


def test_clean_text_whitespace_and_nbsp():
    assert c.clean_text("  Hello \n\t  World\xa0! ") == "Hello World !"
    assert c.clean_text("   ") is None and c.clean_text(None) is None


def test_mojibake_is_repaired():
    assert c.clean_text("Â£51.77") == "£51.77"
    assert c.clean_text("â€œHiâ€\x9d") == "“Hi”" or "Hi" in c.clean_text("â€œHiâ€\x9d")


@pytest.mark.parametrize("raw,expected", [
    ("£51.77", 51.77), ("Â£12.00", 12.0), ("$1,234.50", 1234.5), ("12,5", 12.5),
    ("1,234", 1234.0), (" 7 ", 7.0), (None, None), ("free", None), ("", None)])
def test_parse_price(raw, expected):
    assert c.parse_price(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("star-rating Three", 3.0), ("star-rating One", 1.0), ("4", 4.0), ("4/5", 4.0),
    (5, 5.0), ("star-rating", None), (None, None), ("7", 7.0)])
def test_parse_rating(raw, expected):
    assert c.parse_rating(raw) == expected


def test_normalize_url():
    assert c.normalize_url("HTTPS://Books.ToScrape.com/a.html#frag") == "https://books.toscrape.com/a.html"
    assert c.normalize_url("page-2.html", base="https://x.com/catalogue/page-1.html") == "https://x.com/catalogue/page-2.html"
    assert c.normalize_url("ftp://x.com/a") is None and c.normalize_url("not a url") is None


def test_tags_and_quotes():
    assert c.normalize_tags(["Love", " love ", "LIFE", ""]) == ["love", "life"]
    assert c.normalize_tags("a|b, a") == ["a", "b"]
    assert c.strip_wrapping_quotes("“Hello”") == "Hello"
    assert c.strip_wrapping_quotes("It's") == "It's"


def test_clean_record_flags_bad_values():
    rec = c.clean_record({"source": " Books to Scrape ", "source_url": "javascript:x", "name_or_title": " A  B ",
                          "price": "abc", "rating": "star-rating", "tags": None})
    assert rec["name_or_title"] == "A B" and rec["price"] is None and rec["tags"] == []
    assert {i.split(":")[0] for i in rec["_issues"]} == {"invalid_url", "invalid_price", "invalid_rating"}


def test_clean_record_currency_and_missing_tokens():
    rec = c.clean_record({"source": "S", "source_url": "https://a.com/x", "name_or_title": "T",
                          "price": "Â£5.10", "category": "N/A", "author": "null"})
    assert rec["price"] == 5.1 and rec["currency"] == "GBP" and rec["category"] is None and rec["author"] is None
