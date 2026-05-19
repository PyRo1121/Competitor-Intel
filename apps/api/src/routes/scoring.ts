import type { Database } from "bun:sqlite";
import { Hono } from "hono";
import { getDB } from "../db";

const app = new Hono();

app.get("/", (c) => {
  const db = getDB();
  const rawLimit = Number(c.req.query("limit"));
  const limit = Math.min(
    Math.max(Number.isFinite(rawLimit) ? rawLimit : 50, 1),
    200,
  );

  const companies = db
    .prepare(
      `
    SELECT c.id, c.name, c.slug, c.industry, c.status, c.score,
           (SELECT COUNT(*) FROM funding_rounds WHERE company_id = c.id) as funding_rounds,
           (SELECT COUNT(*) FROM job_postings WHERE company_id = c.id AND is_active = 1) as active_jobs,
           (SELECT COUNT(*) FROM intelligence_events WHERE company_id = c.id) as events
    FROM companies c
    WHERE c.score IS NOT NULL
    ORDER BY c.score DESC NULLS LAST
    LIMIT ?
  `,
    )
    .all(limit);

  return c.json({ companies, count: companies.length, limit });
});

app.get("/:id", (c) => {
  const db = getDB();
  const id = c.req.param("id");

  const company = db.prepare("SELECT * FROM companies WHERE id = ?").get(id);
  if (!company) return c.json({ error: "Company not found" }, 404);

  const breakdown = computeBreakdown(db, id);

  return c.json({
    company_id: id,
    company_name: company.name,
    composite_score: company.score ?? 0,
    breakdown,
    computed_at: company.last_scored_at,
  });
});

function computeBreakdown(db: Database, companyId: string): Record<string, number> {
  const funding = db.prepare(
    `SELECT COUNT(*) as rounds, COALESCE(SUM(amount_usd), 0) as total
     FROM funding_rounds WHERE company_id = ?`
  ).get(companyId);

  const github = db.prepare(
    `SELECT COALESCE(star_growth_30d, 0) as stars, COALESCE(contributor_count, 0) as contributors,
            COALESCE(commits_last_30d, 0) as commits
     FROM github_metrics WHERE company_id = ? ORDER BY extracted_at DESC LIMIT 1`
  ).get(companyId);

  const jobs = db.prepare(
    `SELECT COUNT(*) as count FROM job_postings WHERE company_id = ? AND is_active = 1`
  ).get(companyId);

  const team = db.prepare(
    `SELECT COUNT(*) as count FROM team_members WHERE company_id = ?`
  ).get(companyId);

  const tech = db.prepare(
    `SELECT COUNT(DISTINCT technology) as count FROM technology_stack WHERE company_id = ?`
  ).get(companyId);

  const signals = db.prepare(
    `SELECT COUNT(*) as count FROM raw_signals WHERE company_id = ?`
  ).get(companyId);

  const events = db.prepare(
    `SELECT COUNT(*) as count FROM intelligence_events WHERE company_id = ?`
  ).get(companyId);

  const fundingScore = funding.rounds > 0
    ? Math.min((funding.total / 500_000_000) * 0.6 + 0.4, 1)
    : 0.2;

  const stars = github?.stars || 0;
  const contributors = github?.contributors || 0;
  const efficiencyScore = contributors > 0 ? Math.min((stars / contributors) / 500, 1) : 0.2;

  const signalScore = Math.min((signals?.count || 0) / 50, 1);
  const eventScore = Math.min((events?.count || 0) / 10, 1);
  const tractionScore = signalScore * 0.5 + eventScore * 0.3 + 0.2;

  const commits = github?.commits || 0;
  const techCount = tech?.count || 0;
  const depthScore = Math.min(commits / 200, 1) * 0.6 + Math.min(techCount / 20, 1) * 0.4;

  const hiringScore = Math.min((jobs?.count || 0) / 15, 1) * 0.6 + Math.min((team?.count || 0) / 5, 1) * 0.4;

  const moatScore = techCount > 10 ? 0.5 + Math.min(techCount / 50, 0.3) : techCount > 3 ? 0.3 + Math.min(techCount / 20, 0.2) : 0.2;

  return {
    funding_round_quality: fundingScore,
    investor_tier: fundingScore * 0.8,
    capital_raised_runway: fundingScore * 0.7,
    capital_efficiency: efficiencyScore,
    product_traction: tractionScore,
    revenue_monetization: tractionScore * 0.6,
    technical_depth: depthScore,
    founder_team_quality: Math.min((team?.count || 0) / 5, 1) * 0.7 + 0.3,
    talent_hiring_velocity: hiringScore,
    market_timing_tam: Math.min((signals?.count || 0) / 30, 1) * 0.5 + 0.4,
    competitive_moat: moatScore,
    momentum_risk: Math.min((events?.count || 0) / 10, 1) * 0.6 + 0.2,
  };
}

export default app;
