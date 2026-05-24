import { zValidator } from "@hono/zod-validator";
import { z } from "zod";
import { Hono } from "hono";
import { companyNumericId, resolveCompany } from "../companyResolve";
import { getDB } from "../db";

const jobsQuery = z.object({
  limit: z.coerce.number().int().min(1).max(500).default(50),
  active: z.enum(["true", "false"]).default("true"),
});

const app = new Hono();

app.get("/", zValidator("query", jobsQuery), (c) => {
  const db = getDB();
  const { limit, active } = c.req.valid("query");

  const jobs = db
    .prepare(
      `
    SELECT jp.*, c.name as company_name, c.slug as company_slug,
           (SELECT COUNT(*) FROM job_posting_skills jps WHERE jps.job_posting_id = jp.id) AS skill_count
    FROM job_postings jp
    JOIN companies c ON c.id = jp.company_id
    WHERE jp.is_active = ?
    ORDER BY jp.posted_at DESC, jp.corroboration_score DESC
    LIMIT ?
  `,
    )
    .all(active === "true" ? 1 : 0, limit);

  const stats = db
    .prepare(
      `
    SELECT
      COUNT(*) AS total_postings,
      SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) AS active_postings,
      (SELECT COUNT(*) FROM job_posting_claims) AS total_claims,
      (SELECT COUNT(*) FROM job_posting_skills) AS total_skills,
      (SELECT COUNT(*) FROM company_job_boards WHERE is_verified = 1) AS verified_boards
    FROM job_postings
  `,
    )
    .get();

  return c.json({ jobs, stats, count: jobs.length });
});

/** Per-source job observations (granular layer). */
app.get("/claims", (c) => {
  const db = getDB();
  const companyId = c.req.query("company_id");
  const limit = Math.min(parseInt(c.req.query("limit") || "100", 10), 500);

  let sql = `
    SELECT jpc.*, c.name AS company_name,
           (SELECT COUNT(*) FROM job_posting_skills jps
            WHERE jps.job_posting_claim_id = jpc.id) AS skill_count
    FROM job_posting_claims jpc
    JOIN companies c ON c.id = jpc.company_id
  `;
  const params: (string | number)[] = [];
  if (companyId) {
    sql += " WHERE jpc.company_id = ?";
    params.push(parseInt(companyId, 10));
  }
  sql += " ORDER BY jpc.source_weight DESC, jpc.extracted_at DESC LIMIT ?";
  params.push(limit);

  const claims = db.prepare(sql).all(...params);
  const claimIds = claims.map((r: { id: number }) => r.id);
  const skillsByClaim: Record<number, unknown[]> = {};
  if (claimIds.length) {
    const ph = claimIds.map(() => "?").join(",");
    const skills = db
      .prepare(`SELECT * FROM job_posting_skills WHERE job_posting_claim_id IN (${ph})`)
      .all(...claimIds);
    for (const s of skills) {
      const cid = (s as { job_posting_claim_id: number }).job_posting_claim_id;
      if (!skillsByClaim[cid]) skillsByClaim[cid] = [];
      skillsByClaim[cid].push(s);
    }
  }

  return c.json({
    claims: claims.map((claim: { id: number }) => ({
      ...claim,
      skills: skillsByClaim[claim.id] ?? [],
    })),
  });
});

/** Canonical posting with all supporting claims and skills. */
app.get("/postings/:id", (c) => {
  const db = getDB();
  const id = parseInt(c.req.param("id"), 10);
  const posting = db
    .prepare(
      `
    SELECT jp.*, c.name AS company_name, c.website AS company_website
    FROM job_postings jp
    JOIN companies c ON c.id = jp.company_id
    WHERE jp.id = ?
  `,
    )
    .get(id);

  if (!posting) return c.json({ error: "Posting not found" }, 404);

  const claims = db
    .prepare(
      `
    SELECT * FROM job_posting_claims
    WHERE job_posting_id = ? OR (company_id = ? AND job_posting_id IS NULL)
    ORDER BY source_weight DESC
  `,
    )
    .all(id, (posting as { company_id: number }).company_id);

  const skills = db
    .prepare(`SELECT * FROM job_posting_skills WHERE job_posting_id = ? ORDER BY skill`)
    .all(id);

  let fieldsProvenance: unknown = {};
  try {
    fieldsProvenance = JSON.parse(
      String((posting as { fields_provenance?: string }).fields_provenance || "{}"),
    );
  } catch {
    fieldsProvenance = {};
  }

  return c.json({
    posting: { ...posting, fields_provenance: fieldsProvenance },
    claims,
    skills,
  });
});

app.get("/company/:companyId", (c) => {
  const db = getDB();
  const param = c.req.param("companyId");
  const companyRow = resolveCompany(db, param);
  if (!companyRow) return c.json({ error: "Company not found" }, 404);
  const companyId = companyNumericId(companyRow);

  const jobs = db
    .prepare(
      `
    SELECT jp.*,
           (SELECT COUNT(*) FROM job_posting_skills jps WHERE jps.job_posting_id = jp.id) AS skill_count
    FROM job_postings jp
    WHERE jp.company_id = ? AND jp.is_active = 1
      AND LOWER(jp.title) NOT LIKE '%template%'
    ORDER BY jp.posted_at DESC, jp.seniority_band, jp.title
  `,
    )
    .all(companyId);

  const stats = db
    .prepare(
      `
    SELECT
      COUNT(*) as total_active,
      COUNT(DISTINCT department) as departments_hiring,
      COUNT(DISTINCT location) as locations,
      COUNT(DISTINCT seniority_band) as seniority_levels,
      COUNT(DISTINCT remote_policy) as remote_policies
    FROM job_postings
    WHERE company_id = ? AND is_active = 1
      AND LOWER(title) NOT LIKE '%template%'
  `,
    )
    .get(companyId);

  const boards = db
    .prepare(`SELECT * FROM company_job_boards WHERE company_id = ? ORDER BY last_job_count DESC`)
    .all(companyId);

  const velocity = db
    .prepare(
      `
    SELECT * FROM job_velocity_snapshots
    WHERE company_id = ?
    ORDER BY snapshot_date DESC
    LIMIT 30
  `,
    )
    .all(companyId);

  const skillMix = db
    .prepare(
      `
    SELECT jps.skill, jps.category, COUNT(*) AS mention_count
    FROM job_posting_skills jps
    JOIN job_postings jp ON jp.id = jps.job_posting_id
    WHERE jp.company_id = ? AND jp.is_active = 1
    GROUP BY jps.skill, jps.category
    ORDER BY mention_count DESC
    LIMIT 40
  `,
    )
    .all(companyId);

  const recentHires = db
    .prepare(
      `
    SELECT name, role, joined_date
    FROM team_members
    WHERE company_id = ? AND joined_date >= date('now', '-90 days')
    ORDER BY joined_date DESC
  `,
    )
    .all(companyId);

  return c.json({
    company: companyRow.name,
    company_id: companyId,
    company_slug: companyRow.slug,
    jobs,
    stats,
    job_boards: boards,
    velocity_history: velocity,
    skill_mix: skillMix,
    recent_hires: recentHires,
  });
});

app.get("/trends", (c) => {
  const db = getDB();

  const trends = db
    .prepare(
      `
    SELECT
      c.id AS company_id,
      c.name,
      COUNT(CASE WHEN jp.posted_at >= date('now', '-30 days') THEN 1 END) as jobs_30d,
      COUNT(CASE WHEN jp.posted_at >= date('now', '-90 days') THEN 1 END) as jobs_90d,
      COUNT(CASE WHEN jp.is_active = 1 THEN 1 END) as active_openings,
      COUNT(DISTINCT CASE WHEN jp.is_active = 1 THEN jp.department END) AS departments,
      COUNT(DISTINCT CASE WHEN jp.is_active = 1 THEN jp.seniority_band END) AS seniority_levels
    FROM companies c
    LEFT JOIN job_postings jp ON jp.company_id = c.id
    GROUP BY c.id
    HAVING active_openings > 0
    ORDER BY active_openings DESC
  `,
    )
    .all();

  return c.json({ trends });
});

export default app;
