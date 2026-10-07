"""Record-level validation. Returns a list of human-readable error codes (empty = valid)."""
from typing import List

import config
from processing.cleaning import normalize_url


def validate_record(record: dict) -> List[str]:
    errors: List[str] = list(record.get("_issues", []))   # problems found while cleaning
    source = record.get("source")

    if source not in config.KNOWN_SOURCES:
        errors.append(f"unknown_source:{source}")
    if not record.get("name_or_title"):
        errors.append("missing_name_or_title")
    if not record.get("source_url"):
        if not any(e.startswith("invalid_url") for e in errors):
            errors.append("missing_source_url")
    elif normalize_url(record["source_url"]) is None:
        errors.append("invalid_source_url")

    price = record.get("price")
    if price is not None and (not isinstance(price, (int, float)) or price < 0):
        errors.append(f"price_out_of_range:{price}")

    rating = record.get("rating")
    if rating is not None and not (config.RATING_MIN <= rating <= config.RATING_MAX):
        errors.append(f"rating_out_of_range:{rating}")

    # Source-specific requirements ("required fields where applicable")
    if source == config.BOOKS_SOURCE_NAME:
        if price is None and not any(e.startswith("invalid_price") for e in errors):
            errors.append("missing_price")
        if rating is None and not any(e.startswith("invalid_rating") for e in errors):
            errors.append("missing_rating")
    elif source == config.QUOTES_SOURCE_NAME:
        if not record.get("author"):
            errors.append("missing_author")
    return errors


def reason_codes(errors: List[str]) -> List[str]:
    """'invalid_price:abc' -> 'invalid_price' (for aggregating counts in the summary)."""
    return [e.split(":", 1)[0] for e in errors]
