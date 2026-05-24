/**
 * /health schema gate (6-B10).
 */
import { describe, expect, test } from "bun:test";
import { Database } from "bun:sqlite";
import { join } from "path";
import { missingRequiredTables } from "../src/requiredTables";

describe("missingRequiredTables", () => {
  test("detects absent core tables", () => {
    const db = new Database(":memory:");
    db.exec("CREATE TABLE companies (id INTEGER PRIMARY KEY)");
    const missing = missingRequiredTables(db);
    expect(missing).toContain("raw_signals");
    expect(missing).toContain("funding_rounds");
    db.close();
  });

  test("empty when all required tables exist", () => {
    const root = join(import.meta.dir, "../../..");
    const dbPath = process.env.CI_DB_PATH ?? join(root, "data/ci_test.db");
    const db = new Database(dbPath, { readonly: true });
    const missing = missingRequiredTables(db);
    db.close();
    expect(missing).toEqual([]);
  });
});
