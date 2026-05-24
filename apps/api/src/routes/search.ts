import { zValidator } from "@hono/zod-validator";
import { Hono } from "hono";
import { getDB } from "../db";
import { searchQuery } from "../schemas";
import { runSemanticSearch } from "../semanticSearch";

const app = new Hono();

function keywordSearch(
  db: ReturnType<typeof getDB>,
  q: string,
  limit: number,
  filters: {
    event_type?: string;
    company_id?: number;
    min_confidence?: number;
  },
) {
  const pattern = `%${q}%`;
  const eventClauses = [
    "(ie.event_type LIKE ? OR c.name LIKE ? OR ie.description LIKE ? OR ie.lead_investor LIKE ?)",
  ];
  const eventParams: (string | number)[] = [pattern, pattern, pattern, pattern];
  if (filters.event_type) {
    eventClauses.push("ie.event_type = ?");
    eventParams.push(filters.event_type);
  }
  if (filters.company_id) {
    eventClauses.push("ie.company_id = ?");
    eventParams.push(filters.company_id);
  }
  if (filters.min_confidence !== undefined) {
    eventClauses.push("ie.confidence >= ?");
    eventParams.push(filters.min_confidence);
  }
  eventParams.push(limit);

  const companies = db
    .prepare(
      `SELECT id, name, slug, industry, website, description, score, github_stars
       FROM companies
       WHERE name LIKE ? OR industry LIKE ? OR description LIKE ?
       ORDER BY score DESC NULLS LAST, github_stars DESC
       LIMIT ?`,
    )
    .all(pattern, pattern, pattern, limit);

  const events = db
    .prepare(
      `SELECT ie.*, c.name as company_name
       FROM intelligence_events ie
       LEFT JOIN companies c ON c.id = ie.company_id
       WHERE ${eventClauses.join(" AND ")}
       ORDER BY ie.created_at DESC
       LIMIT ?`,
    )
    .all(...eventParams);

  const signals = db
    .prepare(
      `SELECT rs.id, rs.source, rs.signal_type, rs.detected_at, rs.processed,
              c.name as company_name
       FROM raw_signals rs
       LEFT JOIN companies c ON c.id = rs.company_id
       WHERE rs.data_json LIKE ?
       ORDER BY rs.detected_at DESC
       LIMIT ?`,
    )
    .all(pattern, limit);

  return { companies, events, signals };
}

app.get("/", zValidator("query", searchQuery), async (c) => {
  const db = getDB();
  const { q, limit, mode, event_type, company_id, min_confidence } = c.req.valid("query");
  const filters = { event_type, company_id, min_confidence };

  const useSemantic = mode === "semantic" || mode === "auto";

  if (useSemantic) {
    const semantic = await runSemanticSearch(q, limit);
    if (semantic) {
      return c.json({
        query: q,
        mode: "semantic",
        companies: semantic.companies,
        events: semantic.events,
        funding: semantic.funding,
        top_results: semantic.top_results,
        signals: [],
      });
    }
    if (mode === "semantic") {
      return c.json(
        {
          query: q,
          mode: "semantic",
          error: "semantic_search_unavailable",
          hint: "Ensure Ollama is running with nomic-embed-text, or use mode=keyword",
          companies: [],
          events: [],
          funding: [],
          top_results: [],
          signals: [],
        },
        503,
      );
    }
  }

  const keyword = keywordSearch(db, q, limit, filters);
  return c.json({
    query: q,
    mode: "keyword",
    ...keyword,
    funding: [],
    top_results: [],
  });
});

export default app;
