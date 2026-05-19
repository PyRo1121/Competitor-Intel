import { zValidator } from "@hono/zod-validator";
import { Hono } from "hono";
import { getDB } from "../db";
import { signalQuery } from "../schemas";
import { signalLabelFromRow } from "../signalDisplay";

const app = new Hono();

app.get("/", zValidator("query", signalQuery), (c) => {
  const db = getDB();
  const { limit, offset, source, processed } = c.req.valid("query");

  let sql = `SELECT rs.*, c.name as company_name
             FROM raw_signals rs
             LEFT JOIN companies c ON c.id = rs.company_id
             WHERE 1=1`;
  const params: (string | number)[] = [];

  if (source) {
    sql += ` AND rs.source = ?`;
    params.push(source);
  }
  if (processed !== undefined) {
    sql += ` AND rs.processed = ?`;
    params.push(processed === "true" ? 1 : 0);
  }

  sql += ` ORDER BY rs.detected_at DESC LIMIT ? OFFSET ?`;
  params.push(limit, offset);

  const rows = db.prepare(sql).all(...params) as Array<{
    signal_type: string;
    data_json: string;
    [key: string]: unknown;
  }>;
  const signals = rows.map((row) => ({
    ...row,
    signal_label: signalLabelFromRow(row.signal_type, row.data_json),
  }));
  const { count } = db.prepare(`SELECT COUNT(*) as count FROM raw_signals`).get() as { count: number };

  return c.json({ signals, count, limit, offset });
});

export default app;
