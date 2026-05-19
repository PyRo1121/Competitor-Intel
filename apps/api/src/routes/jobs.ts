import { zValidator } from "@hono/zod-validator";
import { z } from "zod";
import { Hono } from "hono";
import { getDB } from "../db";

const jobsQuery = z.object({
  limit: z.coerce.number().int().min(1).max(200).default(50),
  active: z.enum(["true", "false"]).default("true"),
});

const app = new Hono();

app.get("/", zValidator("query", jobsQuery), (c) => {
  const db = getDB();
  const { limit, active } = c.req.valid("query");

  const jobs = db.prepare(`
    SELECT jp.*, c.name as company_name, c.slug as company_slug
    FROM job_postings jp
    JOIN companies c ON c.id = jp.company_id
    WHERE jp.is_active = ?
    ORDER BY jp.posted_at DESC
    LIMIT ?
  `).all(active ? 1 : 0, limit);

  return c.json({ jobs, count: jobs.length });
});

app.get("/company/:companyId", (c) => {
  const db = getDB();
  const companyId = c.req.param("companyId");

  const company = db.prepare("SELECT name FROM companies WHERE id = ?").get(companyId);
  if (!company) return c.json({ error: "Company not found" }, 404);

  const jobs = db.prepare(`
    SELECT * FROM job_postings 
    WHERE company_id = ? AND is_active = 1
    ORDER BY posted_at DESC
  `).all(companyId);

  // Hiring velocity stats
  const stats = db.prepare(`
    SELECT 
      COUNT(*) as total_active,
      COUNT(DISTINCT department) as departments_hiring,
      COUNT(DISTINCT location) as locations
    FROM job_postings
    WHERE company_id = ? AND is_active = 1
  `).get(companyId);

  // Recent hires
  const recentHires = db.prepare(`
    SELECT name, role, joined_date
    FROM team_members
    WHERE company_id = ? AND joined_date >= date('now', '-90 days')
    ORDER BY joined_date DESC
  `).all(companyId);

  return c.json({
    company: company.name,
    jobs,
    stats,
    recent_hires: recentHires,
  });
});

app.get("/trends", (c) => {
  const db = getDB();

  const trends = db.prepare(`
    SELECT 
      c.name,
      COUNT(CASE WHEN jp.posted_at >= date('now', '-30 days') THEN 1 END) as jobs_30d,
      COUNT(CASE WHEN jp.posted_at >= date('now', '-90 days') THEN 1 END) as jobs_90d,
      COUNT(CASE WHEN jp.posted_at >= date('now', '-30 days') AND jp.is_active = 1 THEN 1 END) as active_30d
    FROM companies c
    LEFT JOIN job_postings jp ON jp.company_id = c.id
    GROUP BY c.id
    HAVING active_30d > 0
    ORDER BY active_30d DESC
  `).all();

  return c.json({ trends });
});

export default app;
