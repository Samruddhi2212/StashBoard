"""Text categorization service — mirrors the regex logic in content.js.

Used server-side when the extension doesn't provide a category (e.g., during
sync from a device running an older extension version).
"""

import json
import re
from typing import Optional

# ── Regex patterns ────────────────────────────────────────────────────────────
# Keep these in sync with the patterns in extension/content.js

_PATTERNS: dict[str, re.Pattern] = {
    "email":      re.compile(r"^[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+$"),
    "color_hex":  re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"),
    "ip_address": re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$"),
    "url":        re.compile(r"^https?://"),
    "address":    re.compile(
        r"^\d+\s+[\w\s]+(street|st|avenue|ave|boulevard|blvd|drive|dr|"
        r"lane|ln|court|ct|way|place|pl|road|rd)\b",
        re.IGNORECASE,
    ),
    "phone":      re.compile(r"^\+?[\d\s\-()+]{7,20}$"),
}

# Regex for IP address validation (octet range)
_IP_OCTET_RE = re.compile(r"^(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$")

# Characters strongly associated with code
_CODE_CHARS_RE = re.compile(r"[{};()=<>]")


def _is_valid_ip(text: str) -> bool:
    """Returns True only if each octet is in the valid range 0–255."""
    octets = text.split(".")
    return len(octets) == 4 and all(_IP_OCTET_RE.match(o) for o in octets)


def classify(text: str) -> str:
    """Classifies text into one of the Stashboard categories.

    Categories (checked in priority order):
        email, color_hex, ip_address, url, address, phone, json, code, text

    Args:
        text: The raw text to classify. May be multi-line.

    Returns:
        A category string: one of email | phone | url | address | code |
        color_hex | json | ip_address | text.
    """
    t = text.strip()
    if not t:
        return "text"

    # Single-line / structured checks (order matters — most specific first)
    if _PATTERNS["email"].match(t):
        return "email"
    if _PATTERNS["color_hex"].match(t):
        return "color_hex"
    if _PATTERNS["ip_address"].match(t) and _is_valid_ip(t):
        return "ip_address"
    if _PATTERNS["url"].match(t):
        return "url"
    if _PATTERNS["address"].match(t):
        return "address"
    if _PATTERNS["phone"].match(t):
        return "phone"

    # JSON: starts with { or [ and parses successfully
    if re.match(r"^\s*[{\[]", t):
        try:
            json.loads(t)
            return "json"
        except (json.JSONDecodeError, ValueError):
            pass

    # Code heuristic: has programming characters AND more than 2 newlines
    if _CODE_CHARS_RE.search(t) and t.count("\n") > 2:
        return "code"

    return "text"


def classify_batch(texts: list[str]) -> list[str]:
    """Classifies a list of texts, returning a parallel list of categories.

    Args:
        texts: List of text strings to classify.

    Returns:
        List of category strings, one per input text.
    """
    return [classify(t) for t in texts]
