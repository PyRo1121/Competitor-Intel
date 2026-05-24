"""Granular job claims, parsing, and aggregation."""

from __future__ import annotations

import json
import sqlite3

import pytest
from collectors.jobs import job_parser as jp
from collectors.jobs.job_aggregator import aggregate_job_postings, cluster_key
from collectors.jobs.job_enricher import store_job_claim
from db.migrations import apply_runtime_migrations


def test_parse_seniority_and_remote():
    assert jp.parse_seniority_band("Senior Software Engineer") == "senior"
    assert jp.parse_remote_policy("Remote - US") == "remote"
    assert jp.parse_remote_policy("San Francisco, Hybrid") == "hybrid"


def test_parse_salary_range():
    lo, hi, raw = jp.parse_salary_usd("Salary $180k - $220k plus equity")
    assert lo == 180_000
    assert hi == 220_000
    assert raw


def test_extract_tech_stack():
    skills = jp.extract_tech_stack(
        "Staff ML Engineer", "Experience with Python, PyTorch, and Kubernetes required"
    )
    names = {s["skill"] for s in skills}
    assert "python" in names
    assert "pytorch" in names
    assert "kubernetes" in names


@pytest.mark.operational
def test_store_claim_and_aggregate(operational_db):
    conn = sqlite3.connect(operational_db)
    apply_runtime_migrations(conn)
    conn.commit()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO companies (name, slug, website) VALUES ('JobCo', 'jobco', 'https://jobco.com')"
    )
    cid = cur.lastrowid
    assert cid is not None
    company_id = int(cid)
    conn.commit()
    conn.close()

    claim_id, is_new = store_job_claim(
        company_id,
        {
            "title": "Senior Backend Engineer",
            "description": "Python, PostgreSQL, AWS. $160k-$190k. Remote US.",
            "location": "Remote",
            "department": "Engineering",
            "source_url": "https://boards.greenhouse.io/jobco/jobs/123",
            "source": "greenhouse",
            "ats_platform": "greenhouse",
            "external_id": "123",
            "posted_at": "2026-05-01",
        },
    )
    assert is_new
    assert claim_id

    claim_id2, is_new2 = store_job_claim(
        company_id,
        {
            "title": "Senior Backend Engineer",
            "description": "Python stack, remote role",
            "location": "Remote",
            "department": "Engineering",
            "source_url": "https://jobco.com/careers/backend-senior",
            "source": "company_careers",
            "ats_platform": "company_careers",
            "posted_at": "2026-05-02",
        },
    )
    assert is_new2

    agg = aggregate_job_postings()
    assert agg["postings_upserted"] >= 1

    conn = sqlite3.connect(operational_db)
    conn.row_factory = sqlite3.Row
    postings = conn.execute(
        "SELECT * FROM job_postings WHERE company_id = ?", (company_id,)
    ).fetchall()
    claims = conn.execute(
        "SELECT * FROM job_posting_claims WHERE company_id = ?", (company_id,)
    ).fetchall()
    skills = conn.execute(
        """
        SELECT jps.skill FROM job_posting_skills jps
        JOIN job_posting_claims jpc ON jpc.id = jps.job_posting_claim_id
        WHERE jpc.company_id = ?
        """,
        (company_id,),
    ).fetchall()
    conn.close()

    assert len(claims) == 2
    assert len(postings) >= 1
    assert any(r["is_active"] for r in postings)
    assert len(skills) >= 2
    prov = json.loads(postings[0]["fields_provenance"] or "{}")
    assert "title" in prov

    key = cluster_key(company_id, "Senior Backend Engineer", "Remote", "greenhouse", "123")
    assert "greenhouse" in key
