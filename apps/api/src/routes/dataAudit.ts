import { Hono } from "hono";
import { getDB } from "../db";
import {
  DATA_DOMAINS,
  DASHBOARD_SURFACE_AUDIT,
  TRUST_TIER_LABELS,
  type DataDomainDefinition,
  type TrustTier,
} from "../dataAuditRegistry";

const app = new Hono();

function scalar(db: ReturnType<typeof getDB>, sql: string): number {
  const row = db.prepare(sql).get() as { n?: number } | undefined;
  const keys = row ? Object.keys(row) : [];
  const val = row && keys.length ? (row as Record<string, number>)[keys[0]!] : 0;
  return Number(val ?? 0);
}

function auditDomain(
  db: ReturnType<typeof getDB>,
  def: DataDomainDefinition,
  totalCompanies: number,
) {
  const rowCount = scalar(db, def.countSql);
  const companiesWithData = def.companiesWithDataSql
    ? scalar(db, def.companiesWithDataSql)
    : rowCount > 0
      ? Math.min(rowCount, totalCompanies)
      : 0;
  const coveragePct =
    totalCompanies > 0 ? Math.round((companiesWithData / totalCompanies) * 1000) / 10 : 0;

  let fundingVerified = 0;
  let fundingUnverified = 0;
  if (def.id === "funding_rounds") {
    fundingVerified = scalar(
      db,
      "SELECT COUNT(*) FROM funding_rounds WHERE corroboration_score >= 0.45",
    );
    fundingUnverified = scalar(
      db,
      `SELECT COUNT(*) FROM funding_rounds WHERE corroboration_score IS NULL OR corroboration_score < 0.45`,
    );
  }

  return {
    ...def,
    rowCount,
    companiesWithData,
    totalCompanies,
    coveragePct,
    ...(def.id === "funding_rounds" ? { fundingVerified, fundingUnverified } : {}),
  };
}

app.get("/", (c) => {
  const db = getDB();
  const totalCompanies = scalar(db, "SELECT COUNT(*) FROM companies");
  const auditedAt = new Date().toISOString();

  const domains = DATA_DOMAINS.map((d) => auditDomain(db, d, totalCompanies));

  const byTier = (Object.keys(TRUST_TIER_LABELS) as TrustTier[]).map((tier) => ({
    tier,
    ...TRUST_TIER_LABELS[tier],
    domainCount: domains.filter((d) => d.tier === tier).length,
  }));

  const highlights = {
    leadershipEmpty: domains.find((d) => d.id === "team_members")?.rowCount === 0,
    productsEmpty: domains.find((d) => d.id === "products")?.rowCount === 0,
    fundingLowCorroboration: domains.find((d) => d.id === "funding_rounds") as
      | (ReturnType<typeof auditDomain> & {
          fundingVerified?: number;
          fundingUnverified?: number;
        })
      | undefined,
    enrichmentCoveragePct: domains.find((d) => d.id === "company_details")?.coveragePct ?? 0,
    githubCoveragePct: domains.find((d) => d.id === "github_metrics")?.coveragePct ?? 0,
  };

  return c.json({
    auditedAt,
    totalCompanies,
    trustTiers: TRUST_TIER_LABELS,
    byTier,
    domains,
    dashboardSurfaces: DASHBOARD_SURFACE_AUDIT,
    highlights,
    recommendations: [
      "Do not show leadership or registry fields until team_members collector ships with source URLs.",
      "Surface corroboration_score on every round; confidence rises with sources — no dual verified/unverified UI sections.",
      "Label signals/events as monitoring feeds, not confirmed facts.",
      "Prioritize SEC/state officer ingest and backfill executive appointments from Hiring events.",
      "Expand company_details enrichment or remove sparse fields from dossier hero.",
    ],
  });
});

export default app;
