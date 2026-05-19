import { Database } from "bun:sqlite";
import { dirname, join } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const MONOREPO_ROOT = join(__dirname, "../../..");

const DB_PATH =
  process.env.CI_DB_PATH ?? join(MONOREPO_ROOT, "data", "competitor_intel.db");

let db: Database | null = null;

export function getDB(): Database {
  if (!db) {
    db = new Database(DB_PATH, { readonly: true });
    db.exec("PRAGMA journal_mode = WAL");
    db.exec("PRAGMA foreign_keys = ON");
  }
  return db;
}

export function closeDB(): void {
  if (db) {
    db.close();
    db = null;
  }
}
