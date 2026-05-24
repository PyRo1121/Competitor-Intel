/**
 * API rate limit middleware (Track 4 P4-3).
 */
import { beforeAll, describe, expect, test } from "bun:test";
import { join } from "path";

const ROOT = join(import.meta.dir, "../../..");
process.env.CI_DB_PATH = process.env.CI_DB_PATH ?? join(ROOT, "data/ci_test.db");
process.env.CI_API_RATE_LIMIT_RPM = "3";
process.env.CI_SQLITE_BUSY_TIMEOUT_MS = process.env.CI_SQLITE_BUSY_TIMEOUT_MS ?? "1000";

const { app } = await import("../src/index.ts");

describe("rate limit", () => {
  test("GET /health is not rate limited", async () => {
    for (let i = 0; i < 5; i++) {
      const res = await app.request("/health");
      expect(res.status).toBe(200);
    }
  });

  test("returns 429 when exceeding CI_API_RATE_LIMIT_RPM", async () => {
    const statuses: number[] = [];
    for (let i = 0; i < 5; i++) {
      const res = await app.request("/api/status", {
        headers: { "x-forwarded-for": "rate-limit-test-client" },
      });
      statuses.push(res.status);
    }
    expect(statuses.filter((s) => s === 429).length).toBeGreaterThan(0);
    const blocked = await app.request("/api/status", {
      headers: { "x-forwarded-for": "rate-limit-test-client" },
    });
    expect(blocked.status).toBe(429);
    const body = await blocked.json();
    expect(body.error).toBe("Too Many Requests");
  });
});
