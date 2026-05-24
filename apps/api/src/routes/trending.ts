import { Hono } from "hono";
import { getDB } from "../db";

const app = new Hono();

app.get("/", (c) => {
  const db = getDB();
  const rawWindow = Number(c.req.query("window") || "30");
  const windowDays = Number.isFinite(rawWindow)
    ? Math.min(365, Math.max(1, Math.floor(rawWindow)))
    : 30;
  const windowExpr = `-${windowDays} days`;

  const trending = db
    .prepare(
      `
    SELECT c.id, c.name, c.industry,
           (SELECT COUNT(*) FROM intelligence_events WHERE company_id = c.id AND created_at >= datetime('now', ?)) as events_30d,
           (SELECT COUNT(*) FROM raw_signals WHERE company_id = c.id AND detected_at >= datetime('now', ?)) as signals_30d,
           (SELECT COUNT(*) FROM job_postings WHERE company_id = c.id AND is_active = 1) as active_jobs
    FROM companies c
    WHERE c.status = 'active'
    ORDER BY events_30d DESC
    LIMIT 20
  `,
    )
    .all(windowExpr, windowExpr);

  return c.json({ trending, window: windowDays });
});

app.get("/:id", (c) => {
  const db = getDB();
  const id = c.req.param("id");

  const company = db.prepare("SELECT name, industry FROM companies WHERE id = ?").get(id);
  if (!company) return c.json({ error: "Company not found" }, 404);

  const events = db
    .prepare(`
    SELECT event_type, COUNT(*) as count
    FROM intelligence_events
    WHERE company_id = ? AND created_at >= datetime('now', '-30 days')
    GROUP BY event_type
    ORDER BY count DESC
  `)
    .all(id);

  const signals = db
    .prepare(`
    SELECT source, COUNT(*) as count
    FROM raw_signals
    WHERE company_id = ? AND detected_at >= datetime('now', '-30 days')
    GROUP BY source
    ORDER BY count DESC
  `)
    .all(id);

  return c.json({ company, events, signals });
});

export default app;
