"""Optional MongoDB storage (bonus). pymongo is imported lazily so the core pipeline doesn't need it."""
import hashlib
import logging
from datetime import datetime, timezone
from typing import List

from processing.deduplication import record_key

log = logging.getLogger(__name__)


def dedup_hash(record: dict) -> str:
    """Stable id built from the same normalised key used for deduplication."""
    return hashlib.sha1("|".join(record_key(record)).encode("utf-8")).hexdigest()


class MongoStore:
    def __init__(self, uri: str, db_name: str = "scraping", collection: str = "records", client=None):
        if client is None:
            from pymongo import MongoClient           # lazy import
            client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        self.client = client
        self.db = client[db_name]
        self.records = self.db[collection]
        self.runs = self.db[f"{collection}_runs"]

    def save(self, records: List[dict], summary: dict) -> dict:
        """Upsert records by dedup hash (re-runs update instead of duplicating); log the run summary."""
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.client.admin.command("ping")             # fail fast if the server is unreachable
        self.records.create_index("source")
        inserted = updated = 0
        for record in records:                       # ~1,100 docs: simple upserts are fast enough
            result = self.records.update_one(
                {"_id": dedup_hash(record)},
                {"$set": {**record, "last_seen_at": now}, "$setOnInsert": {"first_seen_at": now}},
                upsert=True)
            if result.upserted_id is not None:
                inserted += 1
            else:
                updated += 1
        self.runs.insert_one({"run_at": now, "summary": summary})
        stats = {"database": self.db.name, "collection": self.records.name,
                 "inserted": inserted, "updated": updated, "total_in_collection": self.records.count_documents({})}
        log.info("MongoDB: %s", stats)
        return stats
