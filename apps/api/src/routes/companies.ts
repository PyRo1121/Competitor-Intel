import { zValidator } from "@hono/zod-validator";
import { Hono } from "hono";
import { companyNumericId, resolveCompany } from "../companyResolve";
import { getDB } from "../db";
import { companyQuery } from "../schemas";

const app = new Hono();

app.get("/", zValidator("query", companyQuery), (c) => {
  const db = getDB();
  const { limit, offset, sort } = c.req.valid("query");
  const orderBy = sort === "score" ? "score DESC NULLS LAST, name ASC" : "name ASC";

  const rows = db
    .prepare(
      `SELECT id, name, slug, website, x_handle, github_org, industry, status, score,
              first_tracked_at, last_updated_at
       FROM companies ORDER BY ${orderBy} LIMIT ? OFFSET ?`,
    )
    .all(limit, offset);

  const { count } = db.prepare("SELECT COUNT(*) as count FROM companies").get() as {
    count: number;
  };

  return c.json({ companies: rows, count, limit, offset });
});

/** Profile / team / product / license claims for dossier provenance (Track 2). */
app.get("/:id/profile-claims", (c) => {
  const db = getDB();
  const param = c.req.param("id");
  const company = resolveCompany(db, param);
  if (!company) return c.json({ error: "Company not found" }, 404);
  const id = companyNumericId(company);

  const profile = db
    .prepare(
      `SELECT id, field_key, field_value, source, source_url, source_tier,
              source_weight, extraction_confidence, extracted_at
       FROM company_profile_claims WHERE company_id = ?
       ORDER BY source_weight DESC`,
    )
    .all(id);
  const team = db
    .prepare(
      `SELECT id, name, role, source, source_url, source_tier,
              extraction_confidence, source_weight
       FROM team_member_claims WHERE company_id = ?
       ORDER BY source_weight DESC, extraction_confidence DESC`,
    )
    .all(id);
  const products = db
    .prepare(
      `SELECT id, name, description, source, source_url, source_tier,
              extraction_confidence, source_weight
       FROM product_claims WHERE company_id = ?
       ORDER BY source_weight DESC, extraction_confidence DESC`,
    )
    .all(id);
  const licenses = db
    .prepare(
      `SELECT id, license_type, jurisdiction, source, source_url, source_tier,
              extraction_confidence, source_weight
       FROM license_claims WHERE company_id = ?
       ORDER BY source_weight DESC, extraction_confidence DESC`,
    )
    .all(id);

  return c.json({
    company_id: id,
    profile_claims: profile,
    team_claims: team,
    product_claims: products,
    license_claims: licenses,
  });
});

app.get("/:id", (c) => {
  const db = getDB();
  const param = c.req.param("id");
  const company = resolveCompany(db, param);
  if (!company) return c.json({ error: "Company not found" }, 404);

  const id = companyNumericId(company);

  const detailsRow = db.prepare("SELECT * FROM company_details WHERE company_id = ?").get(id);
  const details = detailsRow
    ? {
        ...detailsRow,
        fields_provenance: (() => {
          try {
            return JSON.parse(
              String((detailsRow as { fields_provenance?: string }).fields_provenance || "{}"),
            );
          } catch {
            return {};
          }
        })(),
      }
    : null;
  const valuation = db
    .prepare(
      `SELECT valuation_usd, valuation_kind, method, confidence, as_of_date, updated_at
       FROM company_valuations WHERE company_id = ?`,
    )
    .get(id);
  const funding = db
    .prepare(
      `SELECT * FROM funding_rounds WHERE company_id = ?
       ORDER BY corroboration_score DESC, announced_date DESC`,
    )
    .all(id);

  const claimRows = db
    .prepare(
      `SELECT funding_round_id, id, source, source_url, source_tier, source_weight,
              is_official, headline, announced_date, amount_usd, lead_investor
       FROM funding_round_claims
       WHERE company_id = ?
       ORDER BY source_weight DESC`,
    )
    .all(id);

  const claimsByRound: Record<number, unknown[]> = {};
  for (const row of claimRows) {
    const rid = row.funding_round_id as number | null;
    if (rid == null) continue;
    if (!claimsByRound[rid]) claimsByRound[rid] = [];
    claimsByRound[rid].push(row);
  }

  const participantRows = db
    .prepare(
      `SELECT rp.*, i.name as investor_name, i.tier as investor_tier, i.name_normalized
       FROM round_participants rp
       JOIN investor_firms i ON i.id = rp.investor_id
       WHERE rp.funding_round_id IN (
         SELECT id FROM funding_rounds WHERE company_id = ?
       )
       ORDER BY rp.is_lead DESC, rp.corroboration_score DESC`,
    )
    .all(id);

  const participantsByRound: Record<number, unknown[]> = {};
  for (const row of participantRows) {
    const rid = row.funding_round_id as number;
    if (!participantsByRound[rid]) participantsByRound[rid] = [];
    participantsByRound[rid].push(row);
  }

  const fundingWithSources = funding.map((round: { id: number }) => ({
    ...round,
    sources: claimsByRound[round.id] ?? [],
    participants: participantsByRound[round.id] ?? [],
  }));

  const products = db
    .prepare(
      `SELECT * FROM products WHERE company_id = ?
       ORDER BY COALESCE(corroboration_score, 0.5) DESC, launch_date DESC`,
    )
    .all(id);
  const team = db
    .prepare(
      `SELECT * FROM team_members WHERE company_id = ?
       ORDER BY COALESCE(corroboration_score, 0.5) DESC, joined_date DESC`,
    )
    .all(id);
  const licenses = db
    .prepare(
      `SELECT * FROM regulatory_licenses WHERE company_id = ?
       ORDER BY COALESCE(corroboration_score, 0.5) DESC, effective_date DESC`,
    )
    .all(id);
  const licenseClaims = db
    .prepare(
      `SELECT id, license_type, jurisdiction, regulator, status, source, source_url,
              source_tier, extraction_confidence, effective_date, snippet
       FROM license_claims WHERE company_id = ?
       ORDER BY COALESCE(extraction_confidence, 0.5) DESC, extracted_at DESC`,
    )
    .all(id);
  const capTable = db
    .prepare(
      `SELECT id, holder_name, holder_normalized, ownership_pct, share_class,
              as_of_date, source, source_url, confidence
       FROM cap_table_holdings WHERE company_id = ?
       ORDER BY COALESCE(ownership_pct, 0) DESC, as_of_date DESC, confidence DESC`,
    )
    .all(id);
  const github = db
    .prepare(`SELECT * FROM github_metrics WHERE company_id = ? ORDER BY extracted_at DESC LIMIT 1`)
    .get(id);
  const tech = db
    .prepare(`SELECT category, technology, confidence FROM technology_stack WHERE company_id = ?`)
    .all(id);
  const competitors = db
    .prepare(
      `SELECT c.name, c.slug, cr.relationship_type, cr.overlap_areas, cr.confidence
       FROM competitor_relationships cr
       JOIN companies c ON c.id = cr.competitor_id
       WHERE cr.company_id = ?`,
    )
    .all(id);

  const summary = db
    .prepare(
      `
    SELECT
      (SELECT COUNT(*) FROM raw_signals WHERE company_id = ?) AS signals,
      (SELECT COUNT(*) FROM intelligence_events WHERE company_id = ?) AS events,
      (SELECT COUNT(*) FROM job_postings WHERE company_id = ? AND is_active = 1
         AND LOWER(title) NOT LIKE '%template%') AS active_jobs,
      (SELECT COUNT(*) FROM funding_rounds WHERE company_id = ?) AS funding_rounds,
      (SELECT COALESCE(SUM(amount_usd), 0) FROM funding_rounds WHERE company_id = ?) AS total_raised_usd,
      (SELECT COALESCE(SUM(amount_usd), 0) FROM funding_rounds WHERE company_id = ?
         AND corroboration_score >= 0.45) AS verified_raised_usd,
      (SELECT MAX(corroboration_score) FROM funding_rounds WHERE company_id = ?) AS max_funding_corroboration,
      (SELECT COALESCE(SUM(official_report_count), 0) FROM funding_rounds WHERE company_id = ?) AS funding_official_reports,
      (SELECT COUNT(*) FROM team_members WHERE company_id = ?) AS team_size,
      (SELECT COUNT(*) FROM products WHERE company_id = ?) AS products,
      (SELECT COUNT(*) FROM regulatory_licenses WHERE company_id = ?) AS licenses
  `,
    )
    .get(id, id, id, id, id, id, id, id, id, id, id) as Record<string, number>;

  const recent_signals = db
    .prepare(
      `SELECT rs.id, rs.source, rs.signal_type, rs.detected_at, rs.data_json,
              COALESCE(ie.confidence, 0.2) AS confidence
       FROM raw_signals rs
       LEFT JOIN intelligence_events ie ON ie.raw_signal_id = rs.id
       WHERE rs.company_id = ?
       ORDER BY rs.detected_at DESC LIMIT 12`,
    )
    .all(id);

  const recent_events = db
    .prepare(
      `SELECT id, event_type, amount_usd, confidence, created_at
       FROM intelligence_events WHERE company_id = ?
       ORDER BY created_at DESC LIMIT 12`,
    )
    .all(id);

  return c.json({
    company,
    details,
    valuation: valuation ?? null,
    funding: fundingWithSources,
    products,
    team,
    licenses,
    license_claims: licenseClaims,
    cap_table: capTable,
    github,
    tech_stack: tech,
    competitors,
    summary,
    recent_signals,
    recent_events,
  });
});

export default app;
