import { Hono } from "hono";
import { getDB } from "../db";

const app = new Hono();

app.get("/", (c) => {
  const db = getDB();
  const source = c.req.query("source");

  let query = `
    SELECT rs.*, c.name as company_name
    FROM raw_signals rs
    LEFT JOIN companies c ON c.id = rs.company_id
    WHERE rs.source LIKE '%discovery%'
  `;
  
  if (source) {
    query += ` AND rs.source = ?`;
  }

  query += ` ORDER BY rs.detected_at DESC LIMIT 50`;

  const discoveries = source ? db.prepare(query).all(source) : db.prepare(query).all();

  return c.json({ discoveries, count: discoveries.length });
});

app.get("/candidates", (c) => {
  const db = getDB();
  const rawLimit = Number(c.req.query("limit"));
  const limit = Math.min(
    Math.max(Number.isFinite(rawLimit) ? rawLimit : 25, 1),
    100,
  );

  const candidates = db
    .prepare(
      `
    SELECT id, name, score, discovery_source, status, signals, score_breakdown, last_updated
    FROM company_candidates
    WHERE status = 'pending'
    ORDER BY score DESC
    LIMIT ?
  `,
    )
    .all(limit);

  return c.json({ candidates, count: candidates.length, limit });
});

app.get("/github-orgs", (c) => {
  const db = getDB();

  const orgs = db.prepare(`
    SELECT DISTINCT 
      json_extract(rs.data_json, '$.metadata.org_name') as org_name,
      json_extract(rs.data_json, '$.metadata.stars') as stars,
      json_extract(rs.data_json, '$.metadata.language') as language,
      json_extract(rs.data_json, '$.metadata.description') as description,
      rs.detected_at
    FROM raw_signals rs
    WHERE rs.source = 'github_discovery'
    ORDER BY CAST(json_extract(rs.data_json, '$.metadata.stars') AS INTEGER) DESC
    LIMIT 20
  `).all();

  return c.json({ orgs });
});

app.get("/product-hunt", (c) => {
  const db = getDB();

  const launches = db.prepare(`
    SELECT rs.*, c.name as company_name
    FROM raw_signals rs
    LEFT JOIN companies c ON c.id = rs.company_id
    WHERE rs.source = 'product_hunt_discovery'
    ORDER BY rs.detected_at DESC
    LIMIT 20
  `).all();

  return c.json({ launches });
});

app.post("/add-company", async (c) => {
  const db = getDB();
  const body = await c.req.json();

  const { name, slug, website, x_handle, github_org, industry } = body;

  if (!name || !slug) {
    return c.json({ error: "name and slug are required" }, 400);
  }

  try {
    const result = db.prepare(`
      INSERT OR IGNORE INTO companies (name, slug, website, x_handle, github_org, industry)
      VALUES (?, ?, ?, ?, ?, ?)
    `).run(name, slug, website || null, x_handle || null, github_org || null, industry || "AI/Productivity");

    if (result.changes === 0) {
      return c.json({ error: "Company already exists", slug }, 409);
    }

    return c.json({ added: true, name, slug }, 201);
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Insert failed";
    return c.json({ error: message }, 500);
  }
});

export default app;
