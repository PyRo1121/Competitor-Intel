"""API-based company enrichment (no HTML scrape)."""

from __future__ import annotations

from collectors.enrichment.company_data import api_enrich as ae


def test_gather_api_profile_merges_sources(monkeypatch):
    monkeypatch.setattr(
        ae,
        "github_org_profile",
        lambda org: {
            "source_url": f"https://api.github.com/orgs/{org}",
            "tech_stack": '["Python"]',
        },
    )
    monkeypatch.setattr(ae, "lookup_sec_company", lambda _name: {})

    rows = ae.gather_api_profile("Acme", "acme")
    sources = {r[0] for r in rows}
    assert sources == {"github_api"}


def test_gather_api_profile_includes_sec(monkeypatch):
    monkeypatch.setattr(ae, "github_org_profile", lambda _org: {})
    monkeypatch.setattr(
        ae,
        "lookup_sec_company",
        lambda _name: {
            "source_url": "https://data.sec.gov/submissions/CIK0000000001.json",
            "legal_name": "ACME INC",
        },
    )

    rows = ae.gather_api_profile("Acme Inc", None)
    assert len(rows) == 1
    assert rows[0][0] == "sec_edgar_api"
