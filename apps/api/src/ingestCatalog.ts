import { readFileSync } from "fs";
import { join } from "path";

export interface IngestCatalog {
  generated: string;
  rssFeedsEnabled: number;
  rssFeedsTotal: number;
  rssFeedsDisabled: number;
  xMonitorQueries: number;
  youtubeChannels: number;
}

/** Repo-root `data/ingest_catalog.json` (regenerate via `make export-ingest-catalog`). */
export function loadIngestCatalog(): IngestCatalog | null {
  const path =
    process.env.CI_INGEST_CATALOG_PATH ??
    join(import.meta.dir, "../../../data/ingest_catalog.json");
  try {
    const raw = readFileSync(path, "utf8");
    return JSON.parse(raw) as IngestCatalog;
  } catch {
    return null;
  }
}
