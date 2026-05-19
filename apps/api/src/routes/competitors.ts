import { Hono } from "hono";
import { getDB } from "../db";

const app = new Hono();

app.get("/", (c) => {
  const db = getDB();
  const rows = db.prepare(
    `SELECT cr.*, c1.name as company_name, c2.name as competitor_name
     FROM competitor_relationships cr
     JOIN companies c1 ON c1.id = cr.company_id
     JOIN companies c2 ON c2.id = cr.competitor_id
     ORDER BY cr.confidence DESC`
  ).all();

  return c.json({ relationships: rows, count: rows.length });
});

app.get("/:id", (c) => {
  const db = getDB();
  const id = c.req.param("id");

  const competitors = db.prepare(
    `SELECT c.name, cr.relationship_type, cr.overlap_areas, cr.confidence
     FROM competitor_relationships cr
     JOIN companies c ON c.id = cr.competitor_id
     WHERE cr.company_id = ?
     ORDER BY cr.confidence DESC`
  ).all(id);

  return c.json({ company_id: id, competitors });
});

export default app;
