import { zValidator } from "@hono/zod-validator";
import { Hono } from "hono";
import { getDB } from "../db";
import { searchQuery } from "../schemas";

const app = new Hono();

app.get("/", zValidator("query", searchQuery), (c) => {
  const db = getDB();
  const { q, limit } = c.req.valid("query");

  const companies = db.prepare(
    `SELECT id, name, industry, website FROM companies WHERE name LIKE ? LIMIT ?`
  ).all(`%${q}%`, limit);

  const events = db.prepare(
    `SELECT ie.*, c.name as company_name
     FROM intelligence_events ie
     LEFT JOIN companies c ON c.id = ie.company_id
     WHERE ie.event_type LIKE ? OR c.name LIKE ?
     ORDER BY ie.created_at DESC LIMIT ?`
  ).all(`%${q}%`, `%${q}%`, limit);

  const signals = db.prepare(
    `SELECT rs.*, c.name as company_name
     FROM raw_signals rs
     LEFT JOIN companies c ON c.id = rs.company_id
     WHERE rs.data_json LIKE ?
     ORDER BY rs.detected_at DESC LIMIT ?`
  ).all(`%${q}%`, limit);

  return c.json({ query: q, companies, events, signals });
});

export default app;
