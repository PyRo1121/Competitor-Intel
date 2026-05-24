import { Database } from "bun:sqlite";
import { dirname, join } from "path";
import { fileURLToPath } from "url";
import type { SemanticSearchPayload } from "./semanticSearch";

const __dirname = dirname(fileURLToPath(import.meta.url));
const MONOREPO_ROOT = join(__dirname, "../../..");
const DEFAULT_MODEL = process.env.CI_OLLAMA_MODEL ?? "qwen3-embedding:4b";
const OLLAMA_BASE = (process.env.OLLAMA_HOST ?? "http://127.0.0.1:11434").replace(/\/$/, "");

function dbPath(): string {
  return process.env.CI_DB_PATH ?? join(MONOREPO_ROOT, "data", "competitor_intel.db");
}

function cosine(a: number[], b: number[]): number {
  let dot = 0;
  let na = 0;
  let nb = 0;
  const n = Math.min(a.length, b.length);
  for (let i = 0; i < n; i++) {
    dot += a[i]! * b[i]!;
    na += a[i]! * a[i]!;
    nb += b[i]! * b[i]!;
  }
  const denom = Math.sqrt(na) * Math.sqrt(nb);
  return denom > 0 ? dot / denom : 0;
}

async function fetchQueryEmbedding(text: string): Promise<number[] | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 12_000);
  try {
    const res = await fetch(`${OLLAMA_BASE}/api/embed`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: DEFAULT_MODEL, input: text }),
      signal: controller.signal,
    });
    if (!res.ok) return null;
    const data = (await res.json()) as {
      embeddings?: number[][];
      embedding?: number[];
    };
    if (data.embeddings?.[0]?.length) return data.embeddings[0];
    if (data.embedding?.length) return data.embedding;
    return null;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

type ScoredRow = Record<string, unknown> & { score: number };

function rankCompanies(db: Database, queryEmb: number[], topK: number): ScoredRow[] {
  const rows = db
    .query(
      `SELECT c.id, c.name, c.slug, c.industry, c.github_stars, c.score,
              cd.description_long, COALESCE(cd.embedding, c.embedding) AS embedding
       FROM companies c
       LEFT JOIN company_details cd ON cd.company_id = c.id
       WHERE COALESCE(cd.embedding, c.embedding) IS NOT NULL
       LIMIT 200`,
    )
    .all() as Record<string, unknown>[];

  const scored: ScoredRow[] = [];
  for (const row of rows) {
    try {
      const emb = JSON.parse(String(row.embedding)) as number[];
      let s = cosine(queryEmb, emb);
      const companyScore = Number(row.score ?? 0);
      s = Math.min(1, s + companyScore * 0.05);
      scored.push({
        type: "company",
        id: row.id,
        name: row.name,
        slug: row.slug,
        industry: row.industry,
        github_stars: row.github_stars,
        score: s,
        description: row.description_long,
      });
    } catch {
      /* skip bad embedding */
    }
  }
  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, topK);
}

function rankFunding(db: Database, queryEmb: number[], topK: number): ScoredRow[] {
  const rows = db
    .query(
      `SELECT fr.id, c.name, c.slug, fr.round_type, fr.amount_usd,
              fr.valuation_usd, fr.lead_investor, fr.embedding
       FROM funding_rounds fr
       JOIN companies c ON c.id = fr.company_id
       WHERE fr.embedding IS NOT NULL
       LIMIT 100`,
    )
    .all() as Record<string, unknown>[];

  const scored: ScoredRow[] = [];
  for (const row of rows) {
    try {
      const emb = JSON.parse(String(row.embedding)) as number[];
      scored.push({
        type: "funding",
        id: row.id,
        company_name: row.name,
        company_slug: row.slug,
        round_type: row.round_type,
        amount_usd: row.amount_usd,
        valuation_usd: row.valuation_usd,
        lead_investor: row.lead_investor,
        score: cosine(queryEmb, emb),
      });
    } catch {
      /* skip */
    }
  }
  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, topK);
}

/**
 * In-process semantic search: Ollama embed HTTP + cosine over stored SQLite embeddings.
 * No Python subprocess (Track 2 X-07).
 */
export async function runNativeSemanticSearch(
  query: string,
  limit: number,
): Promise<SemanticSearchPayload | null> {
  const queryEmb = await fetchQueryEmbedding(query);
  if (!queryEmb) return null;

  let db: Database;
  try {
    db = new Database(dbPath(), { readonly: true });
  } catch {
    return null;
  }

  try {
    const companies = rankCompanies(db, queryEmb, limit);
    const funding = rankFunding(db, queryEmb, limit);
    const top_results = [...companies, ...funding]
      .toSorted((a, b) => b.score - a.score)
      .slice(0, limit);

    return {
      ok: true,
      query,
      mode: "semantic",
      companies,
      funding,
      events: [],
      top_results,
    };
  } finally {
    db.close();
  }
}
