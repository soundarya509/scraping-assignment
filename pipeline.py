"""Orchestration: scrape -> clean -> validate -> deduplicate -> consolidate -> write outputs."""
import csv
import json
import logging
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import config
from processing.cleaning import clean_record
from processing.deduplication import deduplicate
from processing.validation import reason_codes, validate_record

log = logging.getLogger(__name__)


def _csv_row(record: dict, fields: List[str]) -> dict:
    row = {}
    for field in fields:
        value = record.get(field)
        if isinstance(value, list):
            value = "|".join(value)
        row[field] = "" if value is None else value
    return row


def write_csv(path: Path, records: List[dict], fields: List[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:   # BOM so Excel shows £/accents
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow(_csv_row(record, fields))


def run_pipeline(scrapers: list, output_dir, store=None) -> dict:
    started = time.monotonic()
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    sources, valid_records, rejected = {}, [], []

    for scraper in scrapers:
        name = scraper.source_name
        stats = {"collected": 0, "cleaned": 0, "rejected_validation": 0, "rejection_reasons": {},
                 "duplicates_removed": 0, "final": 0, "pages_scraped": 0,
                 "failed_pages": [], "failed_detail_pages": [], "fatal_error": None}
        sources[name] = stats
        log.info("=== Source: %s ===", name)
        try:
            raw_records = scraper.scrape()
        except Exception as exc:                       # keep going with the other sources
            log.exception("Source %s failed completely", name)
            raw_records, stats["fatal_error"] = [], repr(exc)
        stats.update(collected=len(raw_records), pages_scraped=scraper.pages_scraped,
                     failed_pages=scraper.failed_pages, failed_detail_pages=scraper.failed_detail_pages)

        reasons = Counter()
        for raw in raw_records:
            try:
                record = clean_record(raw)
            except Exception as exc:
                log.exception("Cleaning crashed for %s", raw.get("source_url"))
                rejected.append({**raw, "rejection_reasons": f"cleaning_exception:{exc!r}"})
                reasons["cleaning_exception"] += 1
                continue
            stats["cleaned"] += 1
            errors = validate_record(record)
            record.pop("_issues", None)
            if errors:
                log.warning("Rejected %s: %s", record.get("source_url"), "; ".join(errors))
                rejected.append({**record, "rejection_reasons": "; ".join(errors)})
                stats["rejected_validation"] += 1
                reasons.update(reason_codes(errors))
            else:
                valid_records.append(record)
        stats["rejection_reasons"] = dict(reasons)

    unique, duplicates, dup_stats = deduplicate(valid_records)
    for name, stats in sources.items():
        stats["duplicates_removed"] = sum(1 for d in duplicates if d.get("source") == name)
        stats["final"] = sum(1 for u in unique if u.get("source") == name)

    write_csv(output_dir / "final_dataset.csv", unique, config.SCHEMA_FIELDS)
    write_csv(output_dir / "rejected_records.csv", rejected, config.SCHEMA_FIELDS + ["rejection_reasons"])
    write_csv(output_dir / "duplicates_removed.csv", duplicates,
              config.SCHEMA_FIELDS + ["duplicate_of", "duplicate_reason"])

    summary = {
        "run_started_at": started_at,
        "execution_time_seconds": round(time.monotonic() - started, 2),
        "sources": sources,
        "totals": {
            "collected": sum(s["collected"] for s in sources.values()),
            "cleaned": sum(s["cleaned"] for s in sources.values()),
            "rejected_validation": len(rejected),
            "duplicates_removed": len(duplicates),
            "final": len(unique),
        },
        "duplicate_breakdown": dup_stats,
        "validity": {
            "final_rows_with_price": sum(1 for r in unique if r["price"] is not None),
            "final_rows_with_author": sum(1 for r in unique if r["author"]),
            "final_rows_with_category": sum(1 for r in unique if r["category"]),
        },
    }
    if store is not None:                      # optional MongoDB step; never blocks the file outputs
        try:
            summary["storage"] = store.save(unique, summary)
        except Exception as exc:
            log.exception("MongoDB storage failed (CSV/JSON outputs are unaffected)")
            summary["storage"] = {"error": repr(exc)}
    with open(output_dir / "summary_report.json", "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=False)
    log.info("Done: %s", json.dumps(summary["totals"]))
    return summary
