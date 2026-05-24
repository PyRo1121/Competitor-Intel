"""
Honest multi-source confidence (0–1) for private-company intel.

Aligned with industry practice (TriSource cross-verification, VeraCT Scan
source credibility + corroboration, MeridAIn-style diversity/verification split,
VCBacked/Crunchbase multi-source ingestion). See docs/CONFIDENCE_SCORING.md.

Design goals (hard to game, inclusive for private companies):
- Domains deduped — syndication cannot inflate diversity.
- Strong tier requires >=2 independent publisher domains (not filings, not GitHub).
- Mean source quality, not max — one headline cannot max the score.
- Field agreement and temporal spread reward consistent independent reporting.
- Rumors and conflicting amounts penalized; no hidden positive floor.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from .funding_source_trust import normalize_domain

WEIGHTS_VERSION = 3

# Positive components (sum = 1.00). Penalties applied after.
CONFIDENCE_WEIGHTS: dict[str, float] = {
    # Independent publisher domains (sqrt curve — diminishing returns after ~6)
    "independent_domains": 0.24,
    # Mean source_weight across unique domains (VeraCT / NewsBreak credibility tier)
    "source_quality_mean": 0.14,
    # Any company blog or regulatory filing in cluster (VCBacked primary source)
    "official_presence": 0.10,
    # Distinct source_tier values (press_wire + tier1 + rss …)
    "source_tier_diversity": 0.06,
    # Domains with tier weight >= 0.72 (tier1, wires, industry_db, official)
    "high_trust_domain_count": 0.08,
    # Mean extraction_confidence on claims (NLP / parser confidence)
    "extraction_confidence_mean": 0.08,
    # Same lead investor named on >=2 claims (when lead present)
    "lead_investor_agreement": 0.06,
    # Same normalized round type across claims
    "round_type_agreement": 0.04,
    # Claims on >=2 different calendar days (not same-hour syndication burst)
    "temporal_spread_days": 0.06,
    # Claims spanning >=2 ISO weeks
    "temporal_spread_weeks": 0.04,
    # Bonuses (applied in agreement slot)
    "amount_agreement_bonus": 0.10,
}

CONFIDENCE_PENALTIES: dict[str, float] = {
    "amount_disagreement": 0.12,
    "rumor_claim_present": 0.10,
    "low_extraction_mean": 0.06,  # mean extraction_confidence < 0.45
}

# Benefit-only extras when supporting data exists (no penalty if absent).
OPTIONAL_BONUSES: dict[str, float] = {
    "valuation_field_agreement": 0.04,
    "regulatory_source": 0.03,
    "investor_roster_overlap": 0.04,
    "github_activity": 0.02,
    "co_investor_agreement": 0.02,
}
OPTIONAL_BONUS_CAP = 0.12

SINGLE_DOMAIN_SCORE_CAP = 0.38
OFFICIAL_SINGLE_DOMAIN_CAP = 0.55
MIN_DOMAINS_FOR_STRONG = 2
STRONG_SCORE_THRESHOLD = 0.75
HIGH_TRUST_WEIGHT = 0.72


def _field(claim: Mapping[str, Any], key: str, default: Any = None) -> Any:
    try:
        return claim[key]
    except (KeyError, TypeError):
        return default


def _claim_domain(claim: Mapping[str, Any]) -> str | None:
    host = normalize_domain(_field(claim, "source_url"))
    if host:
        return host
    src = _field(claim, "source")
    if src:
        return str(src).strip().lower()
    return None


def _amounts_agree(amounts: list[int], tolerance: float = 0.15) -> bool:
    vals = [a for a in amounts if a and a > 0]
    if len(vals) < 2:
        return True
    lo, hi = min(vals), max(vals)
    if hi == 0:
        return True
    return (hi - lo) / hi <= tolerance


def _norm_lead(value: Any) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", str(value).strip().lower())


def _norm_round_type(value: Any) -> str:
    if not value:
        return ""
    rt = str(value).strip()
    m = re.search(r"series\s*([a-f])", rt, re.I)
    if m:
        return f"series {m.group(1).lower()}"
    return rt.lower()


def _field_agreement(claims: Sequence[Mapping[str, Any]], field: str, normalizer) -> float:
    """1.0 if all non-empty normalized values match; 0.5 if no values to compare."""
    vals = [normalizer(_field(c, field)) for c in claims]
    nonempty = [v for v in vals if v]
    if len(nonempty) < 2:
        return 0.5
    return 1.0 if len(set(nonempty)) == 1 else 0.0


def _valuation_values(claim: Mapping[str, Any]) -> list[int]:
    vals: list[int] = []
    for key in (
        "valuation_usd",
        "post_money_valuation_usd",
        "pre_money_valuation_usd",
    ):
        v = _field(claim, key)
        if v is not None and int(v) > 0:
            vals.append(int(v))
    return vals


def _investor_names_from_claim(claim: Mapping[str, Any]) -> set[str]:
    names: set[str] = set()
    lead = _norm_lead(_field(claim, "lead_investor"))
    if lead:
        names.add(lead)
    raw_co = _field(claim, "co_investors")
    if raw_co:
        try:
            parsed = json.loads(raw_co) if isinstance(raw_co, str) else raw_co
            if isinstance(parsed, list):
                for n in parsed:
                    if n:
                        names.add(_norm_lead(n))
        except (json.JSONDecodeError, TypeError):
            names.add(_norm_lead(raw_co))
    for name in _field(claim, "participant_names") or []:
        if name:
            names.add(_norm_lead(name))
    return names


def _optional_bonuses(
    claims: Sequence[Mapping[str, Any]],
    scoring_context: Mapping[str, Any] | None,
) -> tuple[float, dict[str, float]]:
    """Return (bonus_total, component_map). Never subtracts for missing data."""
    ctx = scoring_context or {}
    components: dict[str, float] = {}
    ob = OPTIONAL_BONUSES

    all_vals: list[int] = []
    claims_with_val = 0
    for c in claims:
        vlist = _valuation_values(c)
        if vlist:
            claims_with_val += 1
            all_vals.extend(vlist)
    if len(all_vals) >= 2 and _amounts_agree(all_vals, tolerance=0.12):
        components["valuation_field_agreement"] = ob["valuation_field_agreement"]

    if any(_field(c, "source_tier") == "regulatory" for c in claims):
        components["regulatory_source"] = ob["regulatory_source"]
    else:
        for c in claims:
            host = normalize_domain(_field(c, "source_url")) or ""
            if "sec.gov" in host:
                components["regulatory_source"] = ob["regulatory_source"]
                break

    roster_sets = [_investor_names_from_claim(c) for c in claims]
    roster_sets = [s for s in roster_sets if s]
    if len(roster_sets) >= 2:
        overlap = roster_sets[0].intersection(*roster_sets[1:])
        if overlap:
            components["investor_roster_overlap"] = ob["investor_roster_overlap"]

    co_sets: list[set[str]] = []
    for c in claims:
        raw_co = _field(c, "co_investors")
        if not raw_co:
            continue
        try:
            parsed = json.loads(raw_co) if isinstance(raw_co, str) else raw_co
            if isinstance(parsed, list) and len(parsed) >= 1:
                co_sets.append({_norm_lead(n) for n in parsed if n})
        except (json.JSONDecodeError, TypeError):
            pass
    if len(co_sets) >= 2:
        shared = co_sets[0].intersection(*co_sets[1:])
        if shared:
            components["co_investor_agreement"] = ob["co_investor_agreement"]

    github = ctx.get("github") if isinstance(ctx.get("github"), Mapping) else None
    if github:
        stars = int(github.get("star_growth_30d") or 0)
        commits = int(github.get("commits_last_30d") or 0)
        contributors = int(github.get("contributor_count") or 0)
        if stars > 0 or commits > 0 or contributors > 0:
            components["github_activity"] = ob["github_activity"]

    raw_total = sum(components.values())
    if raw_total <= OPTIONAL_BONUS_CAP:
        return raw_total, components
    scale = OPTIONAL_BONUS_CAP / raw_total
    scaled = {k: round(v * scale, 3) for k, v in components.items()}
    return OPTIONAL_BONUS_CAP, scaled


def _temporal_spread(claims: Sequence[Mapping[str, Any]]) -> tuple[int, int]:
    days: set[str] = set()
    weeks: set[str] = set()
    for c in claims:
        d = _field(c, "announced_date") or _field(c, "extracted_at")
        if not d:
            continue
        s = str(d)[:10]
        if len(s) < 10:
            continue
        days.add(s)
        try:
            dt = datetime.strptime(s, "%Y-%m-%d")
            iso = dt.isocalendar()
            weeks.add(f"{iso.year}-W{iso.week:02d}")
        except ValueError:
            continue
    return len(days), len(weeks)


def compute_corroboration(
    claims: Sequence[Mapping[str, Any]],
    *,
    scoring_context: Mapping[str, Any] | None = None,
) -> tuple[float, dict[str, Any]]:
    """
    Score 0–1 from independent publisher diversity, source quality, field agreement,
    temporal spread, and penalties for rumors / conflicting amounts.

    Each claim mapping supports funding_round_claims columns plus optional keys
    (`participant_names`, etc.). `scoring_context` may include `github` metrics dict.
    Optional bonuses apply only when supporting fields exist — never penalize absence.
    """
    if not claims:
        return 0.0, {}

    domains: set[str] = set()
    domain_weights: dict[str, float] = {}
    tiers: set[str] = set()
    official = False
    rumor = False
    amounts: list[int] = []
    extractions: list[float] = []

    for c in claims:
        dom = _claim_domain(c)
        if dom:
            domains.add(dom)
            w = float(_field(c, "source_weight") or 0)
            domain_weights[dom] = max(domain_weights.get(dom, 0.0), w)
        tier = _field(c, "source_tier")
        if tier:
            tiers.add(str(tier))
        if _field(c, "is_official"):
            official = True
        if _field(c, "is_rumor"):
            rumor = True
        amt = _field(c, "amount_usd")
        if amt is not None and int(amt) > 0:
            amounts.append(int(amt))
        ext = _field(c, "extraction_confidence")
        if ext is not None:
            extractions.append(float(ext))

    n_domains = len(domains)
    w = CONFIDENCE_WEIGHTS
    p = CONFIDENCE_PENALTIES

    # Sqrt curve: 1 domain ≈ 40% of max diversity points; 6+ domains ≈ 100%
    diversity = math.sqrt(min(n_domains, 6) / 6.0) * w["independent_domains"]

    mean_weight = sum(domain_weights.values()) / len(domain_weights) if domain_weights else 0.0
    quality = mean_weight * w["source_quality_mean"]
    official_boost = w["official_presence"] if official else 0.0

    if len(tiers) >= 2:
        tier_factor = min(len(tiers), 4) / 4.0
    elif n_domains >= 3 and mean_weight >= 0.7:
        # Several tier-1 outlets on one tier label — still diverse publishers
        tier_factor = 0.75
    else:
        tier_factor = min(len(tiers), 4) / 4.0 if tiers else 0.0
    tier_div = tier_factor * w["source_tier_diversity"]
    high_trust = sum(1 for wt in domain_weights.values() if wt >= HIGH_TRUST_WEIGHT)
    high_trust_pts = (min(high_trust, 3) / 3.0) * w["high_trust_domain_count"]

    ext_mean = sum(extractions) / len(extractions) if extractions else 0.55
    extraction_pts = min(ext_mean, 1.0) * w["extraction_confidence_mean"]

    lead_agree = _field_agreement(claims, "lead_investor", _norm_lead)
    lead_pts = lead_agree * w["lead_investor_agreement"]

    round_agree = _field_agreement(claims, "round_type", _norm_round_type)
    round_pts = round_agree * w["round_type_agreement"]

    n_days, n_weeks = _temporal_spread(claims)
    day_pts = (min(max(n_days - 1, 0), 3) / 3.0) * w["temporal_spread_days"]
    week_pts = (min(max(n_weeks - 1, 0), 2) / 2.0) * w["temporal_spread_weeks"]

    amount_agreement = _amounts_agree(amounts)
    amount_pts = w["amount_agreement_bonus"] if amount_agreement else 0.0

    components = {
        "independent_domains": round(diversity, 3),
        "source_quality_mean": round(quality, 3),
        "official_presence": round(official_boost, 3),
        "source_tier_diversity": round(tier_div, 3),
        "high_trust_domain_count": round(high_trust_pts, 3),
        "extraction_confidence_mean": round(extraction_pts, 3),
        "lead_investor_agreement": round(lead_pts, 3),
        "round_type_agreement": round(round_pts, 3),
        "temporal_spread_days": round(day_pts, 3),
        "temporal_spread_weeks": round(week_pts, 3),
        "amount_agreement": round(amount_pts, 3),
    }

    score = sum(components.values())

    opt_total, opt_components = _optional_bonuses(claims, scoring_context)
    if opt_components:
        components["optional_bonuses"] = round(opt_total, 3)
        for key, val in opt_components.items():
            components[f"optional_{key}"] = val
        score += opt_total

    if not amount_agreement and len([a for a in amounts if a]) >= 2:
        score -= p["amount_disagreement"]
        components["penalty_amount_disagreement"] = -p["amount_disagreement"]

    if rumor:
        score -= p["rumor_claim_present"]
        components["penalty_rumor"] = -p["rumor_claim_present"]

    if extractions and ext_mean < 0.45:
        score -= p["low_extraction_mean"]
        components["penalty_low_extraction"] = -p["low_extraction_mean"]

    score = max(0.0, min(1.0, round(score, 3)))

    if n_domains < MIN_DOMAINS_FOR_STRONG:
        cap = OFFICIAL_SINGLE_DOMAIN_CAP if official else SINGLE_DOMAIN_SCORE_CAP
        score = min(score, cap)
        if official and n_domains == 1:
            score = max(score, 0.55)

    meta = {
        "claim_count": len(claims),
        "unique_domains": n_domains,
        "unique_tiers": len(tiers),
        "official_present": official,
        "rumor_present": rumor,
        "amount_agreement": amount_agreement,
        "mean_domain_weight": round(mean_weight, 3),
        "mean_extraction_confidence": round(ext_mean, 3),
        "temporal_days": n_days,
        "temporal_weeks": n_weeks,
        "components": components,
        "weights_version": WEIGHTS_VERSION,
    }
    return score, meta


def confidence_tier(score: float | None) -> str:
    if score is None:
        return "early_signal"
    if score >= STRONG_SCORE_THRESHOLD:
        return "strong"
    if score >= 0.45:
        return "building"
    return "early_signal"
