import { Database } from "bun:sqlite";
import { dirname, join } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const MONOREPO_ROOT = join(__dirname, "../../..");

const DB_PATH = process.env.CI_DB_PATH ?? join(MONOREPO_ROOT, "data", "competitor_intel.db");

let db: Database | null = null;

function applyPragmas(database: Database) {
  const busyMs = process.env.CI_SQLITE_BUSY_TIMEOUT_MS ?? "120000";
  const mmap = process.env.CI_SQLITE_MMAP_BYTES ?? "536870912";
  const cache = process.env.CI_SQLITE_CACHE_KIB ?? "-512000";
  const walCkpt = process.env.CI_SQLITE_WAL_AUTOCHECKPOINT ?? "10000";
  database.exec("PRAGMA journal_mode = WAL");
  database.exec("PRAGMA foreign_keys = ON");
  database.exec("PRAGMA synchronous = NORMAL");
  database.exec("PRAGMA temp_store = MEMORY");
  database.exec(`PRAGMA mmap_size = ${mmap}`);
  database.exec(`PRAGMA cache_size = ${cache}`);
  database.exec(`PRAGMA busy_timeout = ${busyMs}`);
  database.exec(`PRAGMA wal_autocheckpoint = ${walCkpt}`);
  // SQLite 3.46+ — warm planner on long-lived API connection
  try {
    database.exec("PRAGMA optimize = 0x10002");
  } catch {
    /* older SQLite */
  }
}

/** Truncate WAL after large ingest (call from ops/cron, not every request). */
export function checkpointWal(mode: "PASSIVE" | "RESTART" | "FULL" | "TRUNCATE" = "RESTART") {
  const database = getSharedDB();
  database.exec(`PRAGMA wal_checkpoint(${mode})`);
}

/**
 * Shared SQLite handle. Bun cannot open the same file as readonly + writable
 * simultaneously (SQLITE_MISUSE); GET routes use this for reads, mutations use
 * getWriteDB() with requireApiKey() middleware.
 */
function getSharedDB(): Database {
  if (!db) {
    // Bun 1.3.x: omit options for RW; `{ readonly: false }` triggers SQLITE_MISUSE.
    db = new Database(DB_PATH);
    applyPragmas(db);
  }
  return db;
}

/** Read paths (SELECT only). */
export function getDB(): Database {
  return getSharedDB();
}

/** POST/DELETE paths — same connection; auth gate is the write boundary. */
export function getWriteDB(): Database {
  return getSharedDB();
}

export function closeDB(): void {
  if (db) {
    db.close();
    db = null;
  }
}
