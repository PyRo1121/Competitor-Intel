import { zValidator } from "@hono/zod-validator";
import { Hono } from "hono";
import { getDB } from "../db";
import { companyQuery } from "../schemas";

const app = new Hono();

app.get("/", zValidator("query", companyQuery), (c) => {
  const db = getDB();
  const { limit, offset } = c.req.valid("query");

  const rows = db
    .prepare(
      `SELECT id, name, slug, website, x_handle, github_org, industry, status,
              first_tracked_at, last_updated_at
       FROM companies ORDER BY name LIMIT ? OFFSET ?`
    )
    .all(limit, offset);

  const { count } = db.prepare("SELECT COUNT(*) as count FROM companies").get() as { count: number };

  return c.json({ companies: rows, count, limit, offset });
});

app.get("/:id", (c) => {
  const db = getDB();
  const id = c.req.param("id");

  const company = db.prepare("SELECT * FROM companies WHERE id = ?").get(id);
  if (!company) return c.json({ error: "Company not found" }, 404);

  const details = db
    .prepare("SELECT * FROM company_details WHERE company_id = ?")
    .get(id);
  const funding = db
    .prepare(
      `SELECT * FROM funding_rounds WHERE company_id = ? ORDER BY announced_date DESC`
    )
    .all(id);
  const products = db
    .prepare(
      `SELECT * FROM products WHERE company_id = ? ORDER BY launch_date DESC`
    )
    .all(id);
  const team = db
    .prepare(
      `SELECT * FROM team_members WHERE company_id = ? ORDER BY joined_date DESC`
    )
    .all(id);
  const github = db
    .prepare(
      `SELECT * FROM github_metrics WHERE company_id = ? ORDER BY extracted_at DESC LIMIT 1`
    )
    .get(id);
  const tech = db
    .prepare(
      `SELECT category, technology, confidence FROM technology_stack WHERE company_id = ?`
    )
    .all(id);
  const competitors = db
    .prepare(
      `SELECT c.name, cr.relationship_type, cr.overlap_areas, cr.confidence
       FROM competitor_relationships cr
       JOIN companies c ON c.id = cr.competitor_id
       WHERE cr.company_id = ?`
    )
    .all(id);

  return c.json({
    company,
    details,
    funding,
    products,
    team,
    github,
    tech_stack: tech,
    competitors,
  });
});

export default app;
