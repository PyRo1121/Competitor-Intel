"""Shared company-name loading and mention extraction for signal collectors."""

from db.connection import get_conn


def load_company_names() -> list[str]:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT name, slug, x_handle FROM companies")
    names: list[str] = []
    for row in cursor.fetchall():
        name, slug, handle = row
        if name:
            names.append(name)
        if slug:
            names.append(slug.replace("-", " "))
        if handle:
            names.append(handle.lstrip("@"))
    conn.close()
    return names


def extract_company_mentions(text: str, company_names: list[str]) -> list[str]:
    if not text:
        return []
    text_lower = text.lower()
    mentions: list[str] = []
    for company in company_names:
        company_lower = company.lower()
        if len(company_lower) < 3:
            continue
        idx = text_lower.find(company_lower)
        if idx >= 0:
            before = idx == 0 or not text_lower[idx - 1].isalnum()
            after = (
                idx + len(company_lower) >= len(text_lower)
                or not text_lower[idx + len(company_lower)].isalnum()
            )
            if before and after:
                mentions.append(company)
    return list(set(mentions))
