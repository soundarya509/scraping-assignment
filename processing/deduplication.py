"""Duplicate detection: normalised key matching (+ URL matching for item-level URLs)."""
import re
import unicodedata
from typing import List, Optional, Tuple

import config


def normalize_for_matching(text: Optional[str]) -> str:
    """Case-, accent-, punctuation- and whitespace-insensitive form of a string."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[\W_]+", " ", text.casefold())
    return text.strip()


def record_key(record: dict) -> Tuple[str, str, str]:
    return (
        record.get("source") or "",
        normalize_for_matching(record.get("name_or_title")),
        normalize_for_matching(record.get("author")),
    )


def deduplicate(records: List[dict]) -> Tuple[List[dict], List[dict], dict]:
    """Keep the first occurrence; return (unique, removed_duplicates, stats).

    Removed records get 'duplicate_of' (URL of the kept record) and 'duplicate_reason'.
    """
    kept_by_key, kept_by_url = {}, {}
    unique, removed = [], []
    stats = {"exact_after_cleaning": 0, "normalized_match": 0, "url_match": 0}

    for record in records:
        key = record_key(record)
        url = record.get("source_url")
        match, reason = None, None
        if key[1] and key in kept_by_key:
            match = kept_by_key[key]
            reason = ("exact_after_cleaning"
                      if match.get("name_or_title") == record.get("name_or_title")
                      and (match.get("author") or "") == (record.get("author") or "")
                      else "normalized_match")
        elif record.get("source") in config.ITEM_LEVEL_URL_SOURCES and url and (record["source"], url) in kept_by_url:
            match, reason = kept_by_url[(record["source"], url)], "url_match"

        if match is None:
            unique.append(record)
            if key[1]:
                kept_by_key[key] = record
            if url:
                kept_by_url[(record.get("source"), url)] = record
        else:
            stats[reason] += 1
            removed.append({**record, "duplicate_of": match.get("source_url"), "duplicate_reason": reason})
    stats["total_removed"] = len(removed)
    return unique, removed, stats
