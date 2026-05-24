/**
 * Read-path API contract tests (Track 2 P2-1).
 */
import { beforeAll, describe, expect, test } from "bun:test";
import { join } from "path";

const ROOT = join(import.meta.dir, "../../..");
process.env.CI_DB_PATH =
  process.env.CI_DB_PATH ?? join(ROOT, "data/ci_test.db");
process.env.CI_SQLITE_BUSY_TIMEOUT_MS = process.env.CI_SQLITE_BUSY_TIMEOUT_MS ?? "1000";

const { app } = await import("../src/index.ts");

describe("GET /api/status", () => {
  test("returns counts and optional ingest catalog", async () => {
    const res = await app.request("/api/status");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.counts).toBeDefined();
    expect(typeof body.counts.companies).toBe("number");
    expect(Array.isArray(body.topSources)).toBe(true);
    expect(body.enrichQueues).toBeDefined();
    expect(typeof body.enrichQueues.totalPendingApply).toBe("number");
    if (body.ingestCatalog) {
      expect(body.ingestCatalog.rssFeedsEnabled).toBeGreaterThan(0);
    }
  });
});

describe("GET /api/companies", () => {
  test("returns paginated list with slug field", async () => {
    const res = await app.request("/api/companies?limit=5&sort=name");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.companies.length).toBeGreaterThan(0);
    expect(body.companies[0].slug !== undefined).toBe(true);
  });

  test("resolves company by slug or numeric id", async () => {
    const list = await app.request("/api/companies?limit=1");
    const { companies } = await list.json();
    expect(companies.length).toBeGreaterThan(0);
    const first = companies[0];
    const byId = await app.request(`/api/companies/${first.id}`);
    expect(byId.status).toBe(200);
    if (first.slug) {
      const bySlug = await app.request(`/api/companies/${first.slug}`);
      expect(bySlug.status).toBe(200);
      const detail = await bySlug.json();
      expect(detail.company.id).toBe(first.id);
    }
  });

  test("profile-claims returns claim arrays", async () => {
    const list = await app.request("/api/companies?limit=1");
    const { companies } = await list.json();
    expect(companies.length).toBeGreaterThan(0);
    const key = companies[0].slug ?? companies[0].id;
    const res = await app.request(`/api/companies/${key}/profile-claims`);
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(typeof body.company_id).toBe("number");
    expect(Array.isArray(body.profile_claims)).toBe(true);
    expect(Array.isArray(body.team_claims)).toBe(true);
  });
});

describe("GET /api/search", () => {
  test("keyword mode returns structured results", async () => {
    const res = await app.request("/api/search?q=ai&mode=keyword&limit=5");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.mode).toBe("keyword");
    expect(body.query).toBe("ai");
    expect(Array.isArray(body.companies)).toBe(true);
    if (body.companies.length > 0) {
      expect(body.companies[0].name).toBeDefined();
      expect("slug" in body.companies[0]).toBe(true);
    }
  });

  test("rejects empty query", async () => {
    const res = await app.request("/api/search?q=");
    expect(res.status).toBe(400);
  });
});

describe("GET /api/events", () => {
  test("returns paginated events", async () => {
    const res = await app.request("/api/events?limit=3");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body.events)).toBe(true);
    expect(typeof body.count).toBe("number");
    if (body.events.length > 0) {
      const row = body.events[0];
      expect("company_slug" in row).toBe(true);
      expect("source_url" in row).toBe(true);
    }
  });
});

describe("GET /api/signals", () => {
  test("returns signal list", async () => {
    const res = await app.request("/api/signals?limit=5");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body.signals)).toBe(true);
  });
});

describe("GET /api/discovery", () => {
  test("candidates endpoint returns pending list", async () => {
    const res = await app.request("/api/discovery/candidates?limit=5");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body.candidates)).toBe(true);
  });
});

describe("GET /api/alerts", () => {
  test("returns alert rules", async () => {
    const res = await app.request("/api/alerts");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body.rules)).toBe(true);
  });
});

describe("GET /api/team", () => {
  test("returns team members list", async () => {
    const res = await app.request("/api/team?limit=5");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body.team)).toBe(true);
  });
});

describe("GET /api/funding", () => {
  test("returns rounds and stats", async () => {
    const res = await app.request("/api/funding?limit=5");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body.funding)).toBe(true);
    expect(body.stats).toBeDefined();
    expect(typeof body.stats.total_rounds).toBe("number");
  });

  test("claims endpoint returns array", async () => {
    const res = await app.request("/api/funding/claims?limit=5");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body.claims)).toBe(true);
  });
});

describe("GET /api/jobs", () => {
  test("returns postings and stats", async () => {
    const res = await app.request("/api/jobs?limit=5");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body.jobs)).toBe(true);
    expect(body.stats).toBeDefined();
  });
});

describe("GET /api/data-audit", () => {
  test("returns domain audit payload", async () => {
    const res = await app.request("/api/data-audit");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body.domains)).toBe(true);
    expect(body.domains.length).toBeGreaterThan(0);
    expect(typeof body.totalCompanies).toBe("number");
  });
});
