# Confidence scoring

Private companies are scored on **independent evidence**, not filing verification and **not GitHub activity** (most private cos have no public repos). Confidence is a **0–1 score** that rises when more **distinct publishers** report the same fact, agree on key fields, and report over time — without letting syndication or rumor inflate trust.

Implementation: `packages/py-collectors/collectors/enrichment/confidence_scoring.py`  
Propagation: `confidence_sync.py` (events ← funding rounds after aggregation)

## Industry alignment (research summary)

| Practice | How we map it |
|----------|----------------|
| **Multi-source verification** (TriSource, VeraCT Scan, MeridAIn) | Unique publisher domains + mean source credibility + field agreement |
| **Independence** (journalism / oruk-style rules) | Domains deduped; same wire syndicated 6× counts as **one** domain |
| **Crunchbase / PitchBook / VCBacked** | Press + wires + industry DBs + company blog; human/algo merge — not SEC-only |
| **Corroboration over time** | Calendar-day and ISO-week spread (reduces single-burst syndication) |
| **Rumor / low-confidence extraction** | Penalties when `is_rumor` or mean `extraction_confidence` is weak |

**Explicit non-goals**

- **GitHub stars/commits** — poor coverage for private cos; easy to game; not used.
- **Filing-required “verified”** — appropriate for public cos; we use corroboration for private.
- **Raw claim count** — volume without diversity does not increase score.

## Anti-gaming rules

| Risk | Mitigation |
|------|------------|
| Same outlet syndicated 6× | Domains deduped; diversity uses **unique domains** with sqrt curve |
| One TechCrunch post scores “Strong” | **Strong (≥0.75)** requires **≥2 independent domains** |
| One headline maxes tier boost | **Mean** `source_weight` across domains, not `max` |
| Conflicting amounts | **−0.12** penalty; **+0.06** bonus when ≥2 amounts agree within 15% |
| Rumor in cluster | **−0.10** if any claim has `is_rumor` |
| Weak NLP extraction | **−0.06** if mean `extraction_confidence` &lt; 0.45 |

## Optional bonuses (v3, benefit-only)

Capped at **+0.12** total (`OPTIONAL_BONUS_CAP`). Missing data never penalizes.

| Bonus | When it applies |
|-------|------------------|
| `valuation_field_agreement` | ≥2 claims with valuation fields within 12% |
| `regulatory_source` | SEC/regulatory tier or sec.gov host |
| `investor_roster_overlap` | Same named investors on ≥2 claims |
| `co_investor_agreement` | Overlapping co-investor lists |
| `github_activity` | Non-zero stars/commits/contributors (tiny; not a gate) |

## Company valuations (no placeholders)

`company_valuation.py` writes `company_valuations` only when financial signals exist:

1. Reported post-money / round / pre-money on best corroborated round  
2. Estimated from latest round size × round-type multiple (labeled `estimated`)  
3. Reported from `intelligence_events.valuation_usd`  
4. Estimated from total raised × 1.6 (labeled `estimated`)  

No baseline or activity-only guesses. Companies without backing data have **no row**; API returns `valuation: null` and the dashboard shows **—**.

API: `GET /companies/:slug` includes `valuation` when present. Dashboard dossier shows **Valuation** / **Est. valuation** only when backed.

## Weights (v3 base, `weights_version: 3`)

Positive components (sum **1.00**):

| Component | Weight | Signal |
|-----------|--------|--------|
| `independent_domains` | 0.24 | `sqrt(min(domains,6)/6)` — diminishing returns |
| `source_quality_mean` | 0.14 | Mean `source_weight` per unique domain |
| `official_presence` | 0.10 | Company blog or regulatory claim in cluster |
| `source_tier_diversity` | 0.06 | Distinct tiers; 3+ tier-1 domains get partial credit |
| `high_trust_domain_count` | 0.08 | Domains with weight ≥ 0.72 (tier1, wires, official) |
| `extraction_confidence_mean` | 0.08 | Mean parser/NLP confidence on claims |
| `lead_investor_agreement` | 0.06 | Same normalized lead on ≥2 claims |
| `round_type_agreement` | 0.04 | Same normalized round type |
| `temporal_spread_days` | 0.06 | Claims on ≥2 calendar days |
| `temporal_spread_weeks` | 0.04 | Claims in ≥2 ISO weeks |
| `amount_agreement_bonus` | 0.10 | ≥2 amounts within 15% |

Penalties (subtracted after sum, then clamped 0–1):

| Penalty | Value |
|---------|--------|
| `amount_disagreement` | −0.12 |
| `rumor_claim_present` | −0.10 |
| `low_extraction_mean` | −0.06 |

**Single-domain caps** (cannot reach Strong):

- Press/RSS only: max **0.38** (Early signal)
- Company/regulatory on own domain only: floor **0.55** (Building), cap below Strong until another independent domain reports

## UI tiers

| Score | Label |
|-------|--------|
| &lt; 0.45 | Early signal |
| 0.45 – 0.74 | Building |
| ≥ 0.75 | Strong |

## Claim fields used

From `funding_round_claims` (and compatible dicts):

- `source_url`, `source`, `source_weight`, `source_tier`, `is_official`, `is_rumor`
- `amount_usd`, `lead_investor`, `round_type`
- `announced_date` or `extracted_at` (temporal spread)
- `extraction_confidence` (optional; default 0.55 when absent)

## Changing weights

1. Edit `CONFIDENCE_WEIGHTS` / `CONFIDENCE_PENALTIES` and bump `WEIGHTS_VERSION` in `confidence_scoring.py`.
2. Run `uv run pytest tests/test_confidence_scoring.py tests/test_funding_corroboration.py`.
3. Re-run funding aggregation so `corroboration_score` and `intelligence_events.confidence` refresh:

```bash
CI_DB_PATH=data/competitor_intel.db uv run python -c \
  "from collectors.enrichment.funding_aggregator import aggregate_funding_rounds; print(aggregate_funding_rounds())"
```

## Model status (v3)

Base corroboration (eleven components + three penalties) stays stable. v3 adds **optional bonuses** and **company-level valuations** when funding or event data supports a number — never placeholder defaults.

**Higher ROI next** (data quality):

1. Classify more publisher domains in `funding_source_trust.py` (reduces `unknown` tier on real startup press).
2. Extract `valuation_usd` / post-money into claims during enrichment (upgrades estimated → reported).
2. Propagate `is_rumor` from headline text (not only event type).
3. Re-run aggregation after collector improvements.
4. Extend the same corroboration pass to non-funding `intelligence_events` when you prioritize signals UX.

## Pipeline order

1. Collectors → `raw_signals`
2. `signal_processor` → `intelligence_events` (classifier `confidence` seed)
3. `funding_enricher` → `funding_round_claims`
4. `aggregate_funding_rounds` → `corroboration_score` + **`sync_all_event_confidence`**
