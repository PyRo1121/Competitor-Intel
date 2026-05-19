import { Hono } from "hono";
import { getDB } from "../db";

const app = new Hono();

app.get("/", (c) => {
  const db = getDB();

  const companies = db.prepare("SELECT COUNT(*) as count FROM companies").get() as { count: number };
  const signals = db.prepare("SELECT COUNT(*) as count FROM raw_signals").get() as { count: number };
  const events = db.prepare("SELECT COUNT(*) as count FROM intelligence_events").get() as { count: number };
  const funding = db.prepare("SELECT COUNT(*) as count FROM funding_rounds").get() as { count: number };
  const xPosts = db.prepare("SELECT COUNT(*) as count FROM x_posts").get() as { count: number };

  const signals24h = db.prepare(
    `SELECT COUNT(*) as count FROM raw_signals WHERE detected_at >= datetime('now', '-24 hours')`
  ).get() as { count: number };

  const events24h = db.prepare(
    `SELECT COUNT(*) as count FROM intelligence_events WHERE created_at >= datetime('now', '-24 hours')`
  ).get() as { count: number };

  const topSources = db.prepare(
    `SELECT source, COUNT(*) as count FROM raw_signals GROUP BY source ORDER BY count DESC LIMIT 5`
  ).all();

  const recentEvents = db.prepare(
    `SELECT ie.event_type, c.name as company_name, ie.amount_usd, ie.created_at
     FROM intelligence_events ie
     LEFT JOIN companies c ON c.id = ie.company_id
     ORDER BY ie.created_at DESC LIMIT 10`
  ).all();

  return c.json({
    counts: { companies: companies.count, signals: signals.count, events: events.count, funding: funding.count, xPosts: xPosts.count },
    last24h: { signals: signals24h.count, events: events24h.count },
    topSources,
    recentEvents,
  });
});

export default app;
