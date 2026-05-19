import { Hono } from "hono";
import { getDB } from "../db";

const app = new Hono();

app.get("/", (c) => {
  const db = getDB();
  const rows = db.prepare(
    `SELECT fr.*, c.name as company_name
     FROM funding_rounds fr
     LEFT JOIN companies c ON c.id = fr.company_id
     ORDER BY fr.announced_date DESC`
  ).all();

  const stats = db.prepare(
    `SELECT
      COUNT(*) as total_rounds,
      SUM(amount_usd) as total_raised,
      AVG(amount_usd) as avg_round,
      COUNT(DISTINCT company_id) as companies_funded
     FROM funding_rounds WHERE amount_usd IS NOT NULL`
  ).get();

  return c.json({ funding: rows, stats });
});

export default app;
