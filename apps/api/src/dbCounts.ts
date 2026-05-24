import type { Database } from "bun:sqlite";

const OPTIONAL_COUNT_TABLES = ["company_aliases", "cap_table_holdings"] as const;

function tableExists(db: Database, table: string): boolean {
  const row = db
    .prepare(`SELECT 1 AS ok FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1`)
    .get(table) as { ok: number } | null;
  return row?.ok === 1;
}

/** Count rows when migrations may not have run yet (dev/test DBs). */
export function optionalTableCount(db: Database, table: string): number {
  if (!OPTIONAL_COUNT_TABLES.includes(table as (typeof OPTIONAL_COUNT_TABLES)[number])) {
    throw new Error(`optionalTableCount: table not allowlisted: ${table}`);
  }
  if (!tableExists(db, table)) {
    return 0;
  }
  const row = db.prepare(`SELECT COUNT(*) AS n FROM ${table}`).get() as { n: number };
  return row.n;
}
