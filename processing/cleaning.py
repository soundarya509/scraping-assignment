"""Pure, reusable cleaning helpers (no network, no I/O)."""
import re
import unicodedata
from typing import Any, List, Optional
from urllib.parse import urljoin, urlsplit, urlunsplit

import config

NULL_TOKENS = {"", "n/a", "na", "none", "null", "nan", "-", "--", "unknown"}
_RATING_WORDS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
_CURRENCIES = {"£": "GBP", "$": "USD", "€": "EUR"}
_QUOTE_PAIRS = [("\u201c", "\u201d"), ('"', '"'), ("'", "'"), ("\u2018", "\u2019")]


def fix_mojibake(text: str) -> str:
    """Repair UTF-8 text that was decoded as cp1252/latin-1 (e.g. 'Â£' -> '£')."""
    if not any(marker in text for marker in ("Ã", "Â", "â€")):
        return text
    for codec in ("cp1252", "latin-1"):
        try:
            return text.encode(codec).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
    return text


def clean_text(value: Any) -> Optional[str]:
    """Trim, collapse whitespace, NFKC-normalise. Empty -> None."""
    if value is None:
        return None
    text = unicodedata.normalize("NFKC", fix_mojibake(str(value)))
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def normalize_missing(value: Any) -> Optional[str]:
    """clean_text + treat placeholders such as 'N/A' or 'null' as missing."""
    text = clean_text(value)
    return None if text is None or text.lower() in NULL_TOKENS else text


def strip_wrapping_quotes(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    for left, right in _QUOTE_PAIRS:
        if len(text) > 1 and text.startswith(left) and text.endswith(right):
            return text[1:-1].strip() or None
    return text


def detect_currency(raw: Any) -> Optional[str]:
    text = clean_text(raw) or ""
    for symbol, code in _CURRENCIES.items():
        if symbol in text:
            return code
    return None


def parse_price(raw: Any) -> Optional[float]:
    """'£51.77' -> 51.77, '1,234.50' -> 1234.5, '12,5' -> 12.5; unparsable -> None."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return round(float(raw), 2)
    text = clean_text(raw)
    if not text:
        return None
    match = re.search(r"\d[\d.,]*", text)
    if not match:
        return None
    number = match.group(0).rstrip(".,")
    if "," in number and "." in number:
        number = number.replace(",", "")
    elif "," in number:
        number = number.replace(",", ".") if re.fullmatch(r"\d+,\d{1,2}", number) else number.replace(",", "")
    try:
        return round(float(number), 2)
    except ValueError:
        return None


def parse_rating(raw: Any) -> Optional[float]:
    """'star-rating Three' -> 3, '4' -> 4, '4/5' -> 4. Range is NOT enforced here (validation does)."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    text = (clean_text(raw) or "").lower()
    for word, value in _RATING_WORDS.items():
        if re.search(rf"\b{word}\b", text):
            return float(value)
    match = re.search(r"\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else None


def normalize_url(url: Any, base: Optional[str] = None) -> Optional[str]:
    """Absolute http(s) URL with lower-case host and no fragment, else None."""
    text = clean_text(url)
    if not text:
        return None
    if base:
        text = urljoin(base, text)
    parts = urlsplit(text)
    if parts.scheme.lower() not in ("http", "https") or not parts.netloc:
        return None
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))


def normalize_tags(raw: Any) -> List[str]:
    """list or 'a|b, c' -> lower-case, de-duplicated, order-preserving list."""
    if raw is None:
        return []
    items = re.split(r"[|,;]", raw) if isinstance(raw, str) else list(raw)
    seen, tags = set(), []
    for item in items:
        tag = normalize_missing(item)
        if tag and tag.lower() not in seen:
            seen.add(tag.lower())
            tags.append(tag.lower())
    return tags


def clean_record(raw: dict) -> dict:
    """Raw scraper record -> standardised record. Problems are listed in '_issues'."""
    issues: List[str] = []
    url_raw = clean_text(raw.get("source_url"))
    source_url = normalize_url(url_raw)
    if url_raw and source_url is None:
        issues.append(f"invalid_url:{url_raw}")

    price_raw = normalize_missing(raw.get("price"))
    price = parse_price(price_raw)
    if price_raw is not None and price is None:
        issues.append(f"invalid_price:{price_raw}")

    rating_raw = normalize_missing(raw.get("rating"))
    rating = parse_rating(rating_raw)
    if rating is not None and float(rating).is_integer():
        rating = int(rating)            # 3 instead of 3.0 in the CSV
    if rating_raw is not None and rating is None:
        issues.append(f"invalid_rating:{rating_raw}")

    cleaned = {
        "source": clean_text(raw.get("source")),
        "source_url": source_url,
        "name_or_title": strip_wrapping_quotes(clean_text(raw.get("name_or_title"))),
        "category": normalize_missing(raw.get("category")),
        "price": price,
        "currency": detect_currency(price_raw) if price is not None else None,
        "rating": rating,
        "author": normalize_missing(raw.get("author")),
        "tags": normalize_tags(raw.get("tags")),
        "description": normalize_missing(raw.get("description")),
        "availability": normalize_missing(raw.get("availability")),
        "scraped_at": clean_text(raw.get("scraped_at")),
        "_issues": issues,
    }
    return cleaned
