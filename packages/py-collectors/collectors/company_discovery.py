import json
import logging
import sqlite3
from datetime import UTC, datetime

from db.connection import get_conn

logger = logging.getLogger(__name__)

FACTOR_WEIGHTS = {
    "funding_round_quality": 0.08,
    "investor_tier": 0.07,
    "capital_raised_runway": 0.06,
    "capital_efficiency": 0.09,
    "product_traction": 0.12,
    "revenue_monetization": 0.05,
    "technical_depth": 0.13,
    "founder_team_quality": 0.14,
    "talent_hiring_velocity": 0.07,
    "market_timing_tam": 0.09,
    "competitive_moat": 0.08,
    "momentum_risk": 0.12,
}

TIER1_INVESTORS = {
    "a16z",
    "sequoia",
    "benchmark",
    "accel",
    "founders fund",
    "andreessen horowitz",
    "sequoia capital",
}
TIER2_INVESTORS = {
    "lightspeed",
    "kleiner",
    "greylock",
    "index ventures",
    "bessemer",
    "first round",
    "yc",
    "y combinator",
}
TIER3_INVESTORS = {"tiger global", "coatue", "dragoneer", "baillie gifford", "fidelity"}

SERIES_SCORES = {
    "series e": 1.0,
    "series d": 0.95,
    "series c": 0.9,
    "series b": 0.75,
    "series a": 0.6,
    "seed": 0.45,
    "pre-seed": 0.35,
    "series s": 0.4,
    "angel": 0.3,
}

INDUSTRY_TAM = {
    "ai": 0.95,
    "llm": 0.95,
    "generative ai": 0.95,
    "foundation model": 0.9,
    "ai agents": 0.85,
    "ai infrastructure": 0.85,
    "ai productivity": 0.8,
    "developer tools": 0.75,
    "cybersecurity": 0.8,
    "fintech": 0.7,
    "healthcare": 0.65,
    "biotech": 0.7,
    "robotics": 0.75,
    "cloud": 0.8,
    "data": 0.7,
    "saas": 0.75,
}


def calculate_company_score(company_id: int, cursor: sqlite3.Cursor) -> dict:
    scores = {}
    total = 0.0

    # 1. Funding Round Quality - from funding_rounds table
    cursor.execute(
        (
            "SELECT round_type FROM funding_rounds WHERE company_id = ? "
            "ORDER BY announced_date DESC LIMIT 1"
        ),
        (company_id,),
    )
    row = cursor.fetchone()
    funding_type = (row[0] or "").lower() if row else ""
    funding_score = 0.25
    for series, score in SERIES_SCORES.items():
        if series in funding_type:
            funding_score = score
            break
    scores["funding_round_quality"] = funding_score
    total += funding_score * FACTOR_WEIGHTS["funding_round_quality"]

    # 2. Investor Tier - from funding_rounds lead_investor
    cursor.execute(
        (
            "SELECT lead_investor FROM funding_rounds WHERE company_id = ? "
            "AND lead_investor IS NOT NULL"
        ),
        (company_id,),
    )
    investors_text = " ".join(r[0].lower() for r in cursor.fetchall() if r[0])
    investor_score = 0.3
    if any(x in investors_text for x in TIER1_INVESTORS):
        investor_score = 0.9
    elif any(x in investors_text for x in TIER2_INVESTORS):
        investor_score = 0.7
    elif any(x in investors_text for x in TIER3_INVESTORS):
        investor_score = 0.6
    scores["investor_tier"] = investor_score
    total += investor_score * FACTOR_WEIGHTS["investor_tier"]

    # 3. Capital Raised / Runway - from funding_rounds amounts and dates
    cursor.execute(
        (
            "SELECT COALESCE(SUM(amount_usd), 0), MAX(announced_date), COUNT(*) "
            "FROM funding_rounds WHERE company_id = ?"
        ),
        (company_id,),
    )
    total_raised, last_date, round_count = cursor.fetchone() or (0, None, 0)
    runway_score = 0.2
    if total_raised > 0:
        amount_score = min(total_raised / 500_000_000, 1.0)
        recency_score = 0.0
        if last_date:
            try:
                last_dt = datetime.fromisoformat(last_date.replace("Z", "+00:00"))
                months_since = (datetime.now(UTC) - last_dt).days / 30
                recency_score = max(0, 1.0 - months_since / 24)
            except (ValueError, TypeError):
                recency_score = 0.5
        runway_score = amount_score * 0.6 + recency_score * 0.4
    scores["capital_raised_runway"] = runway_score
    total += runway_score * FACTOR_WEIGHTS["capital_raised_runway"]

    # 4. Capital Efficiency - GitHub stars per employee signal
    cursor.execute(
        (
            "SELECT COALESCE(star_growth_30d, 0), COALESCE(contributor_count, 0) "
            "FROM github_metrics WHERE company_id = ? ORDER BY extracted_at DESC LIMIT 1"
        ),
        (company_id,),
    )
    gh_row = cursor.fetchone()
    stars = gh_row[0] if gh_row else 0
    contributors = gh_row[1] if gh_row else 0
    efficiency_score = 0.2
    if stars > 0 and contributors > 0:
        stars_per_contributor = stars / max(contributors, 1)
        efficiency_score = min(stars_per_contributor / 500, 1.0)
    scores["capital_efficiency"] = efficiency_score
    total += efficiency_score * FACTOR_WEIGHTS["capital_efficiency"]

    # 5. Product Traction - signals + events + website snapshots
    cursor.execute(
        "SELECT COUNT(*) FROM raw_signals WHERE company_id = ?",
        (company_id,),
    )
    signal_count = cursor.fetchone()[0]
    cursor.execute(
        "SELECT COUNT(*) FROM intelligence_events WHERE company_id = ?",
        (company_id,),
    )
    event_count = cursor.fetchone()[0]
    cursor.execute(
        "SELECT COUNT(*) FROM website_snapshots WHERE company_id = ?",
        (company_id,),
    )
    snapshot_count = cursor.fetchone()[0]
    traction_score = 0.2
    signal_score = min(signal_count / 50, 1.0)
    event_score = min(event_count / 10, 1.0)
    snapshot_score = min(snapshot_count / 5, 1.0)
    traction_score = signal_score * 0.5 + event_score * 0.3 + snapshot_score * 0.2
    scores["product_traction"] = traction_score
    total += traction_score * FACTOR_WEIGHTS["product_traction"]

    # 6. Revenue Monetization - detect pricing pages, SaaS signals, product launches
    cursor.execute(
        "SELECT data_json FROM raw_signals WHERE company_id = ? LIMIT 30",
        (company_id,),
    )
    revenue_signals = 0
    pricing_detected = False
    for (data_json,) in cursor.fetchall():
        try:
            data = json.loads(data_json or "{}")
            text = " ".join(
                str(data.get(k, "") or "") for k in ("title", "description", "text")
            ).lower()
            if any(
                kw in text
                for kw in [
                    "pricing",
                    "plan",
                    "subscription",
                    "saas",
                    "enterprise",
                    "pay",
                    "premium",
                    "pro tier",
                ]
            ):
                pricing_detected = True
                revenue_signals += 1
            if any(kw in text for kw in ["launch", "released", "announced", "now available"]):
                revenue_signals += 1
        except json.JSONDecodeError:
            pass
    revenue_score = 0.15
    if pricing_detected:
        revenue_score = 0.6 + min(revenue_signals / 10, 0.4)
    elif revenue_signals > 0:
        revenue_score = 0.3 + min(revenue_signals / 5, 0.3)
    scores["revenue_monetization"] = revenue_score
    total += revenue_score * FACTOR_WEIGHTS["revenue_monetization"]

    # 7. Technical Depth - GitHub commits, languages, tech stack
    cursor.execute(
        (
            "SELECT COALESCE(commits_last_30d, 0), COALESCE(primary_language, '') "
            "FROM github_metrics WHERE company_id = ? ORDER BY extracted_at DESC LIMIT 1"
        ),
        (company_id,),
    )
    gh_metrics = cursor.fetchone()
    commits = gh_metrics[0] if gh_metrics else 0
    cursor.execute(
        "SELECT COUNT(DISTINCT technology) FROM technology_stack WHERE company_id = ?",
        (company_id,),
    )
    tech_count = cursor.fetchone()[0]
    depth_score = 0.2
    commit_score = min(commits / 200, 1.0)
    tech_score = min(tech_count / 20, 1.0)
    depth_score = commit_score * 0.6 + tech_score * 0.4
    scores["technical_depth"] = depth_score
    total += depth_score * FACTOR_WEIGHTS["technical_depth"]

    # 8. Founder Team Quality — corroborated team_members only (score floor 0.35)
    team_corroboration_floor = 0.35
    cursor.execute(
        """
        SELECT COUNT(*) FROM team_members
        WHERE company_id = ? AND COALESCE(corroboration_score, 0) >= ?
        """,
        (company_id, team_corroboration_floor),
    )
    team_size = cursor.fetchone()[0]
    cursor.execute(
        """
        SELECT role FROM team_members
        WHERE company_id = ? AND role IS NOT NULL
          AND COALESCE(corroboration_score, 0) >= ?
        """,
        (company_id, team_corroboration_floor),
    )
    roles = [r[0].lower() for r in cursor.fetchall() if r[0]]
    founder_score = 0.2
    has_founder = any("founder" in r or "ceo" in r or "cto" in r for r in roles)
    has_exec = any("vp" in r or "head" in r or "director" in r for r in roles)
    if has_founder and has_exec and team_size >= 3:
        founder_score = 0.9
    elif has_founder and team_size >= 2:
        founder_score = 0.7
    elif has_founder:
        founder_score = 0.5
    elif team_size >= 2:
        founder_score = 0.4
    cursor.execute(
        "SELECT team_size FROM company_details WHERE company_id = ? LIMIT 1",
        (company_id,),
    )
    details_row = cursor.fetchone()
    if details_row and details_row[0]:
        team_size_detail = details_row[0]
        if team_size_detail > team_size:
            founder_score = min(founder_score + 0.1, 1.0)
    scores["founder_team_quality"] = founder_score
    total += founder_score * FACTOR_WEIGHTS["founder_team_quality"]

    # 9. Talent Hiring Velocity - job_postings + team_members growth
    cursor.execute(
        "SELECT COUNT(*) FROM job_postings WHERE company_id = ? AND is_active = 1",
        (company_id,),
    )
    active_jobs = cursor.fetchone()[0]
    cursor.execute(
        (
            "SELECT COUNT(*) FROM team_members WHERE company_id = ? "
            "AND joined_date >= date('now', '-90 days')"
        ),
        (company_id,),
    )
    recent_hires = cursor.fetchone()[0]
    hiring_score = 0.15
    job_score = min(active_jobs / 15, 1.0)
    hire_score = min(recent_hires / 5, 1.0)
    hiring_score = job_score * 0.6 + hire_score * 0.4
    scores["talent_hiring_velocity"] = hiring_score
    total += hiring_score * FACTOR_WEIGHTS["talent_hiring_velocity"]

    # 10. Market Timing / TAM - industry classification + signal velocity
    cursor.execute("SELECT industry FROM companies WHERE id = ?", (company_id,))
    industry_row = cursor.fetchone()
    industry = (industry_row[0] or "").lower() if industry_row else ""
    tam_score = 0.3
    for keyword, score in INDUSTRY_TAM.items():
        if keyword in industry:
            tam_score = score
            break
    cursor.execute(
        (
            "SELECT COUNT(*) FROM raw_signals WHERE company_id = ? "
            "AND detected_at >= datetime('now', '-30 days')"
        ),
        (company_id,),
    )
    recent_30d = cursor.fetchone()[0]
    velocity_bonus = min(recent_30d / 50, 0.2)
    tam_score = min(tam_score + velocity_bonus, 1.0)
    scores["market_timing_tam"] = tam_score
    total += tam_score * FACTOR_WEIGHTS["market_timing_tam"]

    # 11. Competitive Moat - competitor relationships + tech stack depth + GitHub
    cursor.execute(
        "SELECT COUNT(*) FROM competitor_relationships WHERE company_id = ?",
        (company_id,),
    )
    competitor_count = cursor.fetchone()[0]
    cursor.execute(
        "SELECT COUNT(DISTINCT technology) FROM technology_stack WHERE company_id = ?",
        (company_id,),
    )
    tech_depth = cursor.fetchone()[0]
    moat_score = 0.2
    if tech_depth > 10:
        moat_score = 0.5 + min(tech_depth / 50, 0.3)
    elif tech_depth > 3:
        moat_score = 0.3 + min(tech_depth / 20, 0.2)
    if competitor_count > 0:
        moat_score = min(moat_score + 0.1, 1.0)
    if stars > 1000:
        moat_score = min(moat_score + 0.1, 1.0)
    scores["competitive_moat"] = moat_score
    total += moat_score * FACTOR_WEIGHTS["competitive_moat"]

    # 12. Momentum / Risk - recent signals + event velocity
    cursor.execute(
        (
            "SELECT COUNT(*) FROM raw_signals WHERE company_id = ? "
            "AND detected_at >= datetime('now', '-7 days')"
        ),
        (company_id,),
    )
    recent_7d = cursor.fetchone()[0]
    cursor.execute(
        (
            "SELECT COUNT(*) FROM intelligence_events WHERE company_id = ? "
            "AND created_at >= datetime('now', '-7 days')"
        ),
        (company_id,),
    )
    events_7d = cursor.fetchone()[0]
    momentum_score = 0.2
    signal_momentum = min(recent_7d / 20, 1.0)
    event_momentum = min(events_7d / 5, 1.0)
    momentum_score = signal_momentum * 0.6 + event_momentum * 0.4
    scores["momentum_risk"] = momentum_score
    total += momentum_score * FACTOR_WEIGHTS["momentum_risk"]

    final_score = round(total, 4)
    return {
        "score": final_score,
        "breakdown": scores,
        "weighted_total": final_score,
    }


def run_discovery_scan():
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT id, name FROM companies WHERE status = 'active'")
    companies = cursor.fetchall()

    updated = 0
    for company_id, _name in companies:
        result = calculate_company_score(company_id, cursor)
        cursor.execute(
            "UPDATE companies SET score = ?, last_scored_at = ? WHERE id = ?",
            (result["score"], datetime.now(UTC).isoformat(), company_id),
        )
        updated += 1

    conn.commit()
    conn.close()
    logger.info("Scored %d companies with 12-factor VC model (zero placeholders)", updated)


if __name__ == "__main__":
    run_discovery_scan()
