import { zValidator } from "@hono/zod-validator";
import { Hono } from "hono";
import { getDB } from "../db";
import { fundingClaimsQuery, fundingInvestorsQuery, fundingListQuery, idParam } from "../schemas";

const app = new Hono();

app.get("/", zValidator("query", fundingListQuery), (c) => {
  const db = getDB();
  const { company_id, limit } = c.req.valid("query");
  let sql = `
      SELECT fr.*, c.name as company_name,
              (SELECT COUNT(*) FROM funding_round_claims frc
               WHERE frc.funding_round_id = fr.id) AS claim_count,
              (SELECT COUNT(*) FROM round_participants rp
               WHERE rp.funding_round_id = fr.id) AS participant_count
       FROM funding_rounds fr
       LEFT JOIN companies c ON c.id = fr.company_id`;
  const params: (number | string)[] = [];
  if (company_id) {
    sql += " WHERE fr.company_id = ?";
    params.push(company_id);
  }
  sql += " ORDER BY fr.corroboration_score DESC, fr.announced_date DESC LIMIT ?";
  params.push(limit);
  const rows = db.prepare(sql).all(...params);
  const stats = db
    .prepare(
      `SELECT
        COUNT(*) as total_rounds,
        SUM(amount_usd) as total_raised,
        AVG(amount_usd) as avg_round,
        COUNT(DISTINCT company_id) as companies_funded,
        (SELECT COUNT(*) FROM funding_round_claims) as total_claims,
        (SELECT COUNT(*) FROM round_participants) as total_round_participants,
        (SELECT COUNT(*) FROM participant_source_attributions) as total_attributions,
        (SELECT COUNT(*) FROM investor_firms) as investor_firms
       FROM funding_rounds WHERE amount_usd IS NOT NULL`,
    )
    .get();

  return c.json({ funding: rows, stats });
});

/** Per-outlet claims with participant rows (granular source layer). */
app.get("/claims", zValidator("query", fundingClaimsQuery), (c) => {
  const db = getDB();
  const { company_id: companyId, limit } = c.req.valid("query");

  let sql = `
    SELECT frc.*, c.name AS company_name,
           (SELECT COUNT(*) FROM funding_claim_participants fcp
            WHERE fcp.funding_round_claim_id = frc.id) AS participant_count
    FROM funding_round_claims frc
    JOIN companies c ON c.id = frc.company_id
  `;
  const params: (string | number)[] = [];
  if (companyId) {
    sql += " WHERE frc.company_id = ?";
    params.push(companyId);
  }
  sql += " ORDER BY frc.source_weight DESC, frc.extracted_at DESC LIMIT ?";
  params.push(limit);

  const claims = db.prepare(sql).all(...params);

  const claimIds = claims.map((r: { id: number }) => r.id);
  const participantsByClaim: Record<number, unknown[]> = {};
  if (claimIds.length) {
    const placeholders = claimIds.map(() => "?").join(",");
    const parts = db
      .prepare(
        `SELECT fcp.*, i.name AS investor_name, i.tier AS investor_tier
         FROM funding_claim_participants fcp
         LEFT JOIN investor_firms i ON i.id = fcp.investor_id
         WHERE fcp.funding_round_claim_id IN (${placeholders})`,
      )
      .all(...claimIds);
    for (const p of parts) {
      const cid = (p as { funding_round_claim_id: number }).funding_round_claim_id;
      if (!participantsByClaim[cid]) participantsByClaim[cid] = [];
      participantsByClaim[cid].push(p);
    }
  }

  return c.json({
    claims: claims.map((claim: { id: number }) => ({
      ...claim,
      participants: participantsByClaim[claim.id] ?? [],
    })),
  });
});

/** Full canonical round: claims, round participants, per-source attributions, provenance. */
app.get("/rounds/:id", zValidator("param", idParam), (c) => {
  const db = getDB();
  const id = parseInt(c.req.valid("param").id, 10);
  const round = db
    .prepare(
      `SELECT fr.*, c.name AS company_name, c.website AS company_website
       FROM funding_rounds fr
       JOIN companies c ON c.id = fr.company_id
       WHERE fr.id = ?`,
    )
    .get(id);

  if (!round) return c.json({ error: "Round not found" }, 404);

  const claims = db
    .prepare(
      `SELECT * FROM funding_round_claims
       WHERE funding_round_id = ? OR company_id = ?
       ORDER BY source_weight DESC`,
    )
    .all(id, (round as { company_id: number }).company_id);

  const claimIds = claims.map((r: { id: number }) => r.id);
  const claimParticipants: Record<number, unknown[]> = {};
  if (claimIds.length) {
    const ph = claimIds.map(() => "?").join(",");
    const rows = db
      .prepare(
        `SELECT fcp.*, i.name AS investor_name, i.name_normalized, i.tier
         FROM funding_claim_participants fcp
         LEFT JOIN investor_firms i ON i.id = fcp.investor_id
         WHERE fcp.funding_round_claim_id IN (${ph})`,
      )
      .all(...claimIds);
    for (const row of rows) {
      const cid = (row as { funding_round_claim_id: number }).funding_round_claim_id;
      if (!claimParticipants[cid]) claimParticipants[cid] = [];
      claimParticipants[cid].push(row);
    }
  }

  const participants = db
    .prepare(
      `SELECT rp.*, i.name AS investor_name, i.name_normalized, i.tier, i.investor_type
       FROM round_participants rp
       JOIN investor_firms i ON i.id = rp.investor_id
       WHERE rp.funding_round_id = ?
       ORDER BY rp.is_lead DESC, rp.corroboration_score DESC`,
    )
    .all(id);

  const rpIds = participants.map((p: { id: number }) => p.id);
  const attributionsByParticipant: Record<number, unknown[]> = {};
  if (rpIds.length) {
    const ph = rpIds.map(() => "?").join(",");
    const attrs = db
      .prepare(
        `SELECT psa.*, frc.headline, frc.source_tier
         FROM participant_source_attributions psa
         JOIN funding_round_claims frc ON frc.id = psa.funding_round_claim_id
         WHERE psa.round_participant_id IN (${ph})`,
      )
      .all(...rpIds);
    for (const a of attrs) {
      const pid = (a as { round_participant_id: number }).round_participant_id;
      if (!attributionsByParticipant[pid]) attributionsByParticipant[pid] = [];
      attributionsByParticipant[pid].push(a);
    }
  }

  let fieldsProvenance: unknown = null;
  try {
    fieldsProvenance = JSON.parse(
      String((round as { fields_provenance?: string }).fields_provenance || "{}"),
    );
  } catch {
    fieldsProvenance = {};
  }

  return c.json({
    round: {
      ...round,
      fields_provenance: fieldsProvenance,
    },
    claims: claims.map((claim: { id: number }) => ({
      ...claim,
      participants: claimParticipants[claim.id] ?? [],
    })),
    participants: participants.map((p: { id: number }) => ({
      ...p,
      source_attributions: attributionsByParticipant[p.id] ?? [],
    })),
  });
});

/** Global investor firms with round counts. */
app.get("/investors", zValidator("query", fundingInvestorsQuery), (c) => {
  const db = getDB();
  const { limit, tier } = c.req.valid("query");

  let sql = `
    SELECT i.*,
           (SELECT COUNT(*) FROM round_participants rp WHERE rp.investor_id = i.id) AS round_count,
           (SELECT COUNT(*) FROM funding_claim_participants fcp WHERE fcp.investor_id = i.id) AS claim_mention_count
    FROM investor_firms i
  `;
  const params: number[] = [];
  if (tier) {
    sql += " WHERE i.tier = ?";
    params.push(parseInt(tier, 10));
  }
  sql += " ORDER BY round_count DESC, i.tier ASC, i.name LIMIT ?";
  params.push(limit);

  return c.json({ investors: db.prepare(sql).all(...params) });
});

/** Investor profile: rounds participated + every outlet attribution. */
app.get("/investors/:id", (c) => {
  const db = getDB();
  const invId = parseInt(c.req.param("id"), 10);
  const investor = db.prepare("SELECT * FROM investor_firms WHERE id = ?").get(invId);
  if (!investor) return c.json({ error: "Investor not found" }, 404);

  const rounds = db
    .prepare(
      `SELECT rp.*, fr.round_type, fr.amount_usd, fr.announced_date,
              fr.corroboration_score, c.name AS company_name, c.id AS company_id
       FROM round_participants rp
       JOIN funding_rounds fr ON fr.id = rp.funding_round_id
       JOIN companies c ON c.id = fr.company_id
       WHERE rp.investor_id = ?
       ORDER BY fr.announced_date DESC`,
    )
    .all(invId);

  const claimMentions = db
    .prepare(
      `SELECT fcp.*, frc.source_url, frc.source_tier, frc.is_official,
              frc.headline, frc.amount_usd, frc.round_type, c.name AS company_name
       FROM funding_claim_participants fcp
       JOIN funding_round_claims frc ON frc.id = fcp.funding_round_claim_id
       JOIN companies c ON c.id = frc.company_id
       WHERE fcp.investor_id = ?
       ORDER BY frc.source_weight DESC`,
    )
    .all(invId);

  const attributions = db
    .prepare(
      `SELECT psa.*, frc.source_url, frc.headline, fr.round_type, c.name AS company_name
       FROM participant_source_attributions psa
       JOIN round_participants rp ON rp.id = psa.round_participant_id
       JOIN funding_rounds fr ON fr.id = rp.funding_round_id
       JOIN funding_round_claims frc ON frc.id = psa.funding_round_claim_id
       JOIN companies c ON c.id = fr.company_id
       WHERE psa.investor_id = ?
       ORDER BY psa.source_url`,
    )
    .all(invId);

  return c.json({
    investor,
    rounds,
    claim_mentions: claimMentions,
    source_attributions: attributions,
  });
});

/** Team / products / licenses — mounted at /api alongside funding routes. */
export const companyEntities = new Hono();

function queryLimit(raw: string | undefined, fallback = 100): number {
  return Math.min(parseInt(raw || String(fallback), 10) || fallback, 500);
}

function parseCompanyIdQuery(raw: string | undefined): number | null {
  if (!raw) return null;
  const n = parseInt(raw, 10);
  return Number.isFinite(n) ? n : null;
}

companyEntities.get("/team", (c) => {
  const db = getDB();
  const companyId = parseCompanyIdQuery(c.req.query("company_id"));
  const limit = queryLimit(c.req.query("limit"));
  let sql = `
    SELECT tm.*, c.name AS company_name
    FROM team_members tm
    JOIN companies c ON c.id = tm.company_id`;
  const params: (string | number)[] = [];
  if (companyId != null) {
    sql += " WHERE tm.company_id = ?";
    params.push(companyId);
  }
  sql += " ORDER BY COALESCE(tm.corroboration_score, 0.5) DESC, tm.joined_date DESC LIMIT ?";
  params.push(limit);
  const team = db.prepare(sql).all(...params);
  const stats = db
    .prepare("SELECT COUNT(*) AS total, COUNT(DISTINCT company_id) AS companies FROM team_members")
    .get();
  return c.json({ team, stats });
});

companyEntities.get("/team/claims", (c) => {
  const db = getDB();
  const companyId = parseCompanyIdQuery(c.req.query("company_id"));
  const limit = queryLimit(c.req.query("limit"));
  let sql = `
    SELECT tmc.*, c.name AS company_name
    FROM team_member_claims tmc
    JOIN companies c ON c.id = tmc.company_id`;
  const params: (string | number)[] = [];
  if (companyId != null) {
    sql += " WHERE tmc.company_id = ?";
    params.push(companyId);
  }
  sql += " ORDER BY tmc.source_weight DESC, tmc.extracted_at DESC LIMIT ?";
  params.push(limit);
  return c.json({ claims: db.prepare(sql).all(...params) });
});

companyEntities.get("/products", (c) => {
  const db = getDB();
  const companyId = parseCompanyIdQuery(c.req.query("company_id"));
  const limit = queryLimit(c.req.query("limit"));
  let sql = `
    SELECT p.*, c.name AS company_name
    FROM products p
    JOIN companies c ON c.id = p.company_id`;
  const params: (string | number)[] = [];
  if (companyId != null) {
    sql += " WHERE p.company_id = ?";
    params.push(companyId);
  }
  sql += " ORDER BY COALESCE(p.corroboration_score, 0.5) DESC, p.launch_date DESC LIMIT ?";
  params.push(limit);
  const products = db.prepare(sql).all(...params);
  const stats = db
    .prepare("SELECT COUNT(*) AS total, COUNT(DISTINCT company_id) AS companies FROM products")
    .get();
  return c.json({ products, stats });
});

companyEntities.get("/products/claims", (c) => {
  const db = getDB();
  const companyId = parseCompanyIdQuery(c.req.query("company_id"));
  const limit = queryLimit(c.req.query("limit"));
  let sql = `
    SELECT pc.*, c.name AS company_name
    FROM product_claims pc
    JOIN companies c ON c.id = pc.company_id`;
  const params: (string | number)[] = [];
  if (companyId != null) {
    sql += " WHERE pc.company_id = ?";
    params.push(companyId);
  }
  sql += " ORDER BY pc.source_weight DESC, pc.extracted_at DESC LIMIT ?";
  params.push(limit);
  return c.json({ claims: db.prepare(sql).all(...params) });
});

companyEntities.get("/licenses", (c) => {
  const db = getDB();
  const companyId = parseCompanyIdQuery(c.req.query("company_id"));
  const limit = queryLimit(c.req.query("limit"));
  let sql = `
    SELECT rl.*, c.name AS company_name
    FROM regulatory_licenses rl
    JOIN companies c ON c.id = rl.company_id`;
  const params: (string | number)[] = [];
  if (companyId != null) {
    sql += " WHERE rl.company_id = ?";
    params.push(companyId);
  }
  sql += " ORDER BY COALESCE(rl.corroboration_score, 0.5) DESC, rl.effective_date DESC LIMIT ?";
  params.push(limit);
  const licenses = db.prepare(sql).all(...params);
  const stats = db
    .prepare(
      "SELECT COUNT(*) AS total, COUNT(DISTINCT company_id) AS companies FROM regulatory_licenses",
    )
    .get();
  return c.json({ licenses, stats });
});

companyEntities.get("/cap-table", (c) => {
  const db = getDB();
  const companyId = parseCompanyIdQuery(c.req.query("company_id"));
  const limit = queryLimit(c.req.query("limit"));
  let sql = `
    SELECT h.*, c.name AS company_name
    FROM cap_table_holdings h
    JOIN companies c ON c.id = h.company_id`;
  const params: (string | number)[] = [];
  if (companyId != null) {
    sql += " WHERE h.company_id = ?";
    params.push(companyId);
  }
  sql += " ORDER BY COALESCE(h.ownership_pct, 0) DESC, h.as_of_date DESC LIMIT ?";
  params.push(limit);
  const holdings = db.prepare(sql).all(...params);
  const stats = db
    .prepare(
      "SELECT COUNT(*) AS total, COUNT(DISTINCT company_id) AS companies FROM cap_table_holdings",
    )
    .get();
  return c.json({ holdings, stats });
});

companyEntities.get("/licenses/claims", (c) => {
  const db = getDB();
  const companyId = parseCompanyIdQuery(c.req.query("company_id"));
  const limit = queryLimit(c.req.query("limit"));
  let sql = `
    SELECT lc.*, c.name AS company_name
    FROM license_claims lc
    JOIN companies c ON c.id = lc.company_id`;
  const params: (string | number)[] = [];
  if (companyId != null) {
    sql += " WHERE lc.company_id = ?";
    params.push(companyId);
  }
  sql += " ORDER BY lc.source_weight DESC, lc.extracted_at DESC LIMIT ?";
  params.push(limit);
  return c.json({ claims: db.prepare(sql).all(...params) });
});

export default app;
