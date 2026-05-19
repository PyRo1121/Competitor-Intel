import { zValidator } from "@hono/zod-validator";
import { Hono } from "hono";
import { getDB } from "../db";
import { eventQuery } from "../schemas";

const app = new Hono();

app.get("/", zValidator("query", eventQuery), (c) => {
  const db = getDB();
  const { limit, offset, type } = c.req.valid("query");

  let sql = `SELECT ie.*, c.name as company_name
             FROM intelligence_events ie
             LEFT JOIN companies c ON c.id = ie.company_id
             WHERE 1=1`;
  const params: (string | number)[] = [];

  if (type) {
    sql += ` AND ie.event_type = ?`;
    params.push(type);
  }

  sql += ` ORDER BY ie.created_at DESC LIMIT ? OFFSET ?`;
  params.push(limit, offset);

  const rows = db.prepare(sql).all(...params);
  const { count } = db.prepare(`SELECT COUNT(*) as count FROM intelligence_events`).get() as { count: number };

  return c.json({ events: rows, count, limit, offset });
});

export default app;
