import type { Database } from "bun:sqlite";

export type CompanyRow = Record<string, unknown> & {
  id: number;
  name: string;
  slug: string;
};

/** Resolve numeric id or slug to a company row. */
export function resolveCompany(db: Database, param: string): CompanyRow | null {
  if (/^\d+$/.test(param)) {
    const row = db.prepare("SELECT * FROM companies WHERE id = ?").get(Number(param));
    return (row as CompanyRow | null) ?? null;
  }
  const row = db.prepare("SELECT * FROM companies WHERE slug = ?").get(param);
  return (row as CompanyRow | null) ?? null;
}

export function companyNumericId(company: CompanyRow): number {
  return company.id as number;
}
