import { Hono } from "hono";
import { zValidator } from "@hono/zod-validator";
import { z } from "zod";
import { getDB, getWriteDB } from "../db";
import { requireApiKey } from "../middleware/auth";

const app = new Hono();

const createRuleSchema = z.object({
  name: z.string().min(1),
  event_types: z.array(z.string()).min(1),
  channel: z.string().default("discord"),
  company_id: z.number().optional(),
  min_confidence: z.number().min(0).max(1).default(0.5),
});

app.get("/", (c) => {
  const db = getDB();

  const rules = db
    .prepare(`
    SELECT ar.*, c.name as company_name
    FROM alert_rules ar
    LEFT JOIN companies c ON c.id = ar.company_id
    ORDER BY ar.created_at DESC
  `)
    .all();

  return c.json({ rules, count: rules.length });
});

app.get("/recent", (c) => {
  const db = getDB();
  const limit = c.req.query("limit") || "20";

  const alerts = db
    .prepare(`
    SELECT a.*, ie.event_type, ie.confidence, ie.amount_usd, ie.lead_investor,
           c.name as company_name
    FROM alerts_sent a
    JOIN intelligence_events ie ON ie.id = a.event_id
    LEFT JOIN companies c ON c.id = ie.company_id
    ORDER BY a.sent_at DESC
    LIMIT ?
  `)
    .all(parseInt(limit));

  return c.json({ alerts, count: alerts.length });
});

app.post("/", requireApiKey(), zValidator("json", createRuleSchema), (c) => {
  const db = getWriteDB();
  const body = c.req.valid("json");

  const result = db
    .prepare(`
    INSERT INTO alert_rules (name, company_id, event_types, min_confidence, channel, enabled)
    VALUES (?, ?, ?, ?, ?, 1)
  `)
    .run(
      body.name,
      body.company_id ?? null,
      JSON.stringify({ types: body.event_types }),
      body.min_confidence,
      body.channel,
    );

  return c.json({ id: result.lastInsertRowid, ...body }, 201);
});

app.delete("/:id", requireApiKey(), (c) => {
  const db = getWriteDB();
  const id = c.req.param("id");

  const result = db.prepare("DELETE FROM alert_rules WHERE id = ?").run(id);
  if (result.changes === 0) return c.json({ error: "Rule not found" }, 404);

  return c.json({ deleted: true });
});

export default app;
