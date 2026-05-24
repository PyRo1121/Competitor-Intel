import type { Database } from "bun:sqlite";

/** Tables the API and dossier expect after a normal migrate (6-B10). */
export const REQUIRED_TABLES = [
  "companies",
  "raw_signals",
  "intelligence_events",
  "funding_rounds",
  "company_details",
  "license_claims",
] as const;

export function missingRequiredTables(db: Database): string[] {
  const rows = db
    .prepare(
      `SELECT name FROM sqlite_master WHERE type = 'table' AND name IN (${REQUIRED_TABLES.map(() => "?").join(",")})`,
    )
    .all(...REQUIRED_TABLES) as { name: string }[];
  const present = new Set(rows.map((r) => r.name));
  return REQUIRED_TABLES.filter((t) => !present.has(t));
}
