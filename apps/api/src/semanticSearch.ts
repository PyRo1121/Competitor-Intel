import { dirname, join } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const MONOREPO_ROOT = join(__dirname, "../../..");

const SEMANTIC_TIMEOUT_MS = 45_000;

export type SemanticSearchPayload = {
  ok: boolean;
  query: string;
  mode?: string;
  error?: string;
  companies: Record<string, unknown>[];
  funding: Record<string, unknown>[];
  events: Record<string, unknown>[];
  top_results: Record<string, unknown>[];
};

import { runNativeSemanticSearch } from "./nativeSemanticSearch";

/**
 * Semantic search: Bun-native Ollama + stored embeddings first; Python bridge only if
 * CI_SEMANTIC_PYTHON=1 or native path unavailable.
 */
export async function runSemanticSearch(
  query: string,
  limit: number,
): Promise<SemanticSearchPayload | null> {
  if (process.env.CI_SEMANTIC_PYTHON !== "1") {
    const native = await runNativeSemanticSearch(query, limit);
    if (native) return native;
  }

  const dbPath = process.env.CI_DB_PATH ?? join(MONOREPO_ROOT, "data", "competitor_intel.db");

  const proc = Bun.spawn({
    cmd: [
      "uv",
      "run",
      "python",
      "apps/cli/semantic_search.py",
      query,
      "--json",
      "--limit",
      String(limit),
    ],
    cwd: MONOREPO_ROOT,
    env: {
      ...process.env,
      CI_DB_PATH: dbPath,
      PYTHONUNBUFFERED: "1",
    },
    stdout: "pipe",
    stderr: "pipe",
  });

  const timer = setTimeout(() => proc.kill(), SEMANTIC_TIMEOUT_MS);

  try {
    const [stdout, stderr, exitCode] = await Promise.all([
      new Response(proc.stdout).text(),
      new Response(proc.stderr).text(),
      proc.exited,
    ]);

    if (exitCode !== 0) {
      console.warn("semantic_search.py failed:", stderr.slice(0, 500));
      return null;
    }

    const parsed = JSON.parse(stdout) as SemanticSearchPayload;
    if (!parsed.ok) {
      console.warn("semantic search error:", parsed.error);
      return null;
    }
    return parsed;
  } catch (err) {
    console.warn("semantic search bridge error:", err);
    return null;
  } finally {
    clearTimeout(timer);
  }
}
