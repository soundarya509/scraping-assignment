import mongomock
import config
from pipeline import run_pipeline
from scrapers.books_scraper import BooksScraper
from storage import MongoStore, dedup_hash
from tests.fakes import *


def site():
    return FakeClient({BOOKS: books_page([book_card("Example Book Title", "a_1/index.html"),
                                          book_card(" EXAMPLE BOOK TITLE ", "b_2/index.html"),
                                          book_card("Other", "c_3/index.html")])})


def test_mongo_upsert_is_idempotent(tmp_path):
    store = MongoStore("unused", "t", "records", client=mongomock.MongoClient())
    s1 = run_pipeline([BooksScraper(site(), fetch_details=False)], tmp_path, store=store)
    assert s1["storage"]["inserted"] == 2 and store.records.count_documents({}) == 2
    s2 = run_pipeline([BooksScraper(site(), fetch_details=False)], tmp_path, store=store)   # re-run
    assert s2["storage"]["inserted"] == 0 and s2["storage"]["updated"] == 2
    assert store.records.count_documents({}) == 2 and store.runs.count_documents({}) == 2
    doc = store.records.find_one({"name_or_title": "Other"})
    assert doc["_id"] == dedup_hash(doc) and doc["first_seen_at"] and doc["last_seen_at"]


def test_mongo_failure_does_not_break_file_output(tmp_path):
    class Broken:
        def save(self, *a): raise ConnectionError("no mongo")
    s = run_pipeline([BooksScraper(site(), fetch_details=False)], tmp_path, store=Broken())
    assert "error" in s["storage"] and (tmp_path / "final_dataset.csv").exists()
