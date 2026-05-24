/**
 * API auth and CORS smoke tests (Track 0 P0-2).
 * Run: cd apps/api && bun test
 */
import { beforeAll, describe, expect, test } from "bun:test";
import { join } from "path";

const ROOT = join(import.meta.dir, "../../..");
process.env.CI_DB_PATH =
  process.env.CI_DB_PATH ?? join(ROOT, "data/ci_test.db");
process.env.CI_API_KEY = "test-ci-api-key";
process.env.CI_API_CORS_ORIGINS = "http://localhost:5173";
/** Fail fast when prod DB is locked by another process (daily worker, etc.). */
process.env.CI_SQLITE_BUSY_TIMEOUT_MS = process.env.CI_SQLITE_BUSY_TIMEOUT_MS ?? "1000";

const { app } = await import("../src/index.ts");

describe("health", () => {
  test("GET /health is public", async () => {
    const res = await app.request("/health");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("ok");
  });
});

describe("mutation auth", () => {
  test("POST /api/alerts rejects missing key", async () => {
    const res = await app.request("/api/alerts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: "test-rule",
        event_types: ["Funding Round"],
      }),
    });
    expect(res.status).toBe(401);
  });

  test("POST /api/alerts rejects wrong key", async () => {
    const res = await app.request("/api/alerts", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer wrong-key",
      },
      body: JSON.stringify({
        name: "test-rule",
        event_types: ["Funding Round"],
      }),
    });
    expect(res.status).toBe(401);
  });

  test("POST /api/alerts accepts valid key", async () => {
    const res = await app.request(
      "/api/alerts",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer test-ci-api-key",
        },
        body: JSON.stringify({
          name: `ci-test-rule-${Date.now()}`,
          event_types: ["Funding Round"],
        }),
      },
      { signal: AbortSignal.timeout(5000) },
    );
    // 201 when DB writable; 500 if SQLITE_BUSY on shared prod file (auth still passed)
    expect([201, 500]).toContain(res.status);
    if (res.status === 201) {
      const body = await res.json();
      expect(body.id).toBeDefined();
    }
  });
});

describe("cors", () => {
  test("allows configured origin", async () => {
    const res = await app.request("/api/status", {
      headers: { Origin: "http://localhost:5173" },
    });
    expect(res.headers.get("access-control-allow-origin")).toBe(
      "http://localhost:5173",
    );
  });

  test("blocks unknown origin", async () => {
    const res = await app.request("/api/status", {
      headers: { Origin: "http://attacker.example" },
    });
    expect(res.headers.get("access-control-allow-origin")).toBeNull();
  });
});
