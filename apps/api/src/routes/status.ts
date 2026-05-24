import { Hono } from "hono";
import { getDB } from "../db";
import { optionalTableCount } from "../dbCounts";
import { loadIngestCatalog } from "../ingestCatalog";
import { loadEnrichQueues } from "../enrichQueues";

const app = new Hono();

/** Single round-trip status payload — tuned for low latency on local SQLite. */
app.get("/", (c) => {
  const db = getDB();

  const counts = db
    .prepare(
      `
    SELECT
      (SELECT COUNT(*) FROM companies) AS companies,
      (SELECT COUNT(*) FROM raw_signals) AS signals,
      (SELECT COUNT(*) FROM intelligence_events) AS events,
      (SELECT COUNT(*) FROM funding_rounds) AS funding,
      (SELECT COUNT(*) FROM x_posts) AS xPosts,
      (SELECT COUNT(*) FROM company_candidates WHERE status = 'pending') AS pendingCandidates,
      (SELECT COUNT(*) FROM license_claims) AS licenseClaims,
      (SELECT COUNT(*) FROM regulatory_licenses) AS regulatoryLicenses
  `,
    )
    .get() as {
    companies: number;
    signals: number;
    events: number;
    funding: number;
    xPosts: number;
    pendingCandidates: number;
    licenseClaims: number;
    regulatoryLicenses: number;
  };

  const last24h = db
    .prepare(
      `
    SELECT
      (SELECT COUNT(*) FROM raw_signals WHERE detected_at >= datetime('now', '-24 hours')) AS signals,
      (SELECT COUNT(*) FROM intelligence_events WHERE created_at >= datetime('now', '-24 hours')) AS events
  `,
    )
    .get() as { signals: number; events: number };

  const freshness = db
    .prepare(
      `
    SELECT
      (SELECT MAX(detected_at) FROM raw_signals) AS lastSignalAt,
      (SELECT MAX(created_at) FROM intelligence_events) AS lastEventAt,
      (SELECT MAX(posted_at) FROM x_posts) AS lastXAt
  `,
    )
    .get() as {
    lastSignalAt: string | null;
    lastEventAt: string | null;
    lastXAt: string | null;
  };

  const topSources = db
    .prepare(
      `SELECT source, COUNT(*) as count FROM raw_signals GROUP BY source ORDER BY count DESC LIMIT 5`,
    )
    .all();

  const recentEvents = db
    .prepare(
      `SELECT ie.event_type, c.name as company_name, ie.amount_usd, ie.created_at
       FROM intelligence_events ie
       LEFT JOIN companies c ON c.id = ie.company_id
       ORDER BY ie.created_at DESC LIMIT 10`,
    )
    .all();

  const track4Counts = {
    companyAliases: optionalTableCount(db, "company_aliases"),
    capTableHoldings: optionalTableCount(db, "cap_table_holdings"),
  };

  return c.json({
    queriedAt: new Date().toISOString(),
    counts: { ...counts, ...track4Counts },
    last24h,
    freshness,
    topSources,
    recentEvents,
    ingestCatalog: loadIngestCatalog(),
    enrichQueues: loadEnrichQueues(),
  });
});

export default app;
