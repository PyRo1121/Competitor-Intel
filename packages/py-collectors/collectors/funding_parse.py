"""Shared USD amount parsing for collectors, repair, and enrichment."""

from __future__ import annotations

import re


def parse_amount_usd(text: str) -> int | None:
    """Parse a dollar amount from free text (billion / million / K / bare $)."""
    if not text:
        return None
    m = re.search(r"\$?([\d,.]+)\s*(billion|b)\b", text, re.IGNORECASE)
    if m:
        try:
            return int(float(m.group(1).replace(",", "")) * 1_000_000_000)
        except ValueError:
            pass
    m = re.search(r"\$?([\d,.]+)\s*(million|m)\b", text, re.IGNORECASE)
    if m:
        try:
            return int(float(m.group(1).replace(",", "")) * 1_000_000)
        except ValueError:
            pass
    m = re.search(r"\$\s*([\d,.]+)\s*([Kk])\b", text)
    if m:
        try:
            return int(float(m.group(1).replace(",", "")) * 1_000)
        except ValueError:
            pass
    m = re.search(r"\$([\d,]+)\b", text)
    if m:
        try:
            val = int(m.group(1).replace(",", ""))
            if val >= 100_000:
                return val
        except ValueError:
            pass
    return None
