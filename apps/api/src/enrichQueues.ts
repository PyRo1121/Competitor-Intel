import { existsSync, readFileSync } from "fs";
import { join } from "path";

const MONOREPO_ROOT = join(import.meta.dir, "../../..");
const ENRICH_DIR = join(MONOREPO_ROOT, "data", "hermes_enrich");

type QueueFile = { name: string; queue: string; results: string };

const QUEUES: QueueFile[] = [
  { name: "events", queue: "enrich_queue.jsonl", results: "enrich_results.jsonl" },
  { name: "funding", queue: "funding_enrich_queue.jsonl", results: "funding_enrich_results.jsonl" },
  { name: "company", queue: "company_enrich_queue.jsonl", results: "company_enrich_results.jsonl" },
];

function countJsonlLines(path: string): number {
  if (!existsSync(path)) {
    return 0;
  }
  const text = readFileSync(path, "utf8");
  return text.split("\n").filter((line) => line.trim().length > 0).length;
}

/** Hermes enrich queue depth for /api/status (6-H02). */
export function loadEnrichQueues() {
  const queues: Record<
    string,
    { queueLines: number; resultsPresent: boolean; pendingApply: number }
  > = {};
  let totalPending = 0;

  for (const spec of QUEUES) {
    const queuePath = join(ENRICH_DIR, spec.queue);
    const resultsPath = join(ENRICH_DIR, spec.results);
    const queueLines = countJsonlLines(queuePath);
    const resultsPresent = existsSync(resultsPath);
    const pendingApply = resultsPresent ? 0 : queueLines;
    totalPending += pendingApply;
    queues[spec.name] = { queueLines, resultsPresent, pendingApply };
  }

  return { dir: ENRICH_DIR, queues, totalPendingApply: totalPending };
}
