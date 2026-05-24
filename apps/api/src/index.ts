import { Hono } from "hono";
import { cors } from "hono/cors";
import { logger } from "hono/logger";
import { secureHeaders } from "hono/secure-headers";
import { timing } from "hono/timing";
import companies from "./routes/companies";
import signals from "./routes/signals";
import events from "./routes/events";
import funding, { companyEntities } from "./routes/funding";
import status from "./routes/status";
import search from "./routes/search";
import trending from "./routes/trending";
import competitors from "./routes/competitors";
import scoring from "./routes/scoring";
import alerts from "./routes/alerts";
import jobs from "./routes/jobs";
import discovery from "./routes/discovery";
import dataAudit from "./routes/dataAudit";
import { rateLimit } from "./middleware/rateLimit";
import { getDB } from "./db";
import { missingRequiredTables } from "./requiredTables";
const app = new Hono();

const defaultOrigins =
  "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173,http://localhost:3000";
const allowedOrigins = new Set(
  (process.env.CI_API_CORS_ORIGINS ?? defaultOrigins)
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean),
);

app.use(
  "*",
  cors({
    origin: (origin) => {
      if (!origin) {
        return [...allowedOrigins][0];
      }
      return allowedOrigins.has(origin) ? origin : null;
    },
    allowMethods: ["GET", "POST", "DELETE", "OPTIONS"],
    allowHeaders: ["Content-Type", "Authorization", "X-API-Key"],
  }),
);
app.use("*", rateLimit());
app.use("*", logger());
app.use("*", secureHeaders());
app.use("*", timing());

app.onError((err, c) => {
  console.error(err);
  return c.json({ error: "Internal Server Error" }, 500);
});

app.notFound((c) => c.json({ error: "Not Found" }, 404));

app.get("/health", (c) => {
  const missing = missingRequiredTables(getDB());
  if (missing.length > 0) {
    return c.json(
      {
        status: "degraded",
        timestamp: new Date().toISOString(),
        missingTables: missing,
        hint: "Run: make migrate-db or uv run python -c \"from db.schema import init_database; init_database()\"",
      },
      503,
    );
  }
  return c.json({ status: "ok", timestamp: new Date().toISOString() });
});

app.route("/api/companies", companies);
app.route("/api/signals", signals);
app.route("/api/events", events);
app.route("/api/funding", funding);
app.route("/api/status", status);
app.route("/api/search", search);
app.route("/api/competitors", competitors);
app.route("/api/scoring", scoring);
app.route("/api/alerts", alerts);
app.route("/api/jobs", jobs);
app.route("/api/discovery", discovery);
app.route("/api/trending", trending);
app.route("/api/data-audit", dataAudit);
app.route("/api", companyEntities);

app.get("/", (c) =>
  c.json({
    name: "Private Company Intelligence API",
    version: "2.1.0",
    endpoints: [
      "/api/companies",
      "/api/signals",
      "/api/events",
      "/api/funding",
      "/api/funding/claims",
      "/api/funding/rounds/:id",
      "/api/funding/investors",
      "/api/funding/investors/:id",
      "/api/status",
      "/api/search",
      "/api/competitors",
      "/api/scoring",
      "/api/alerts",
      "/api/jobs",
      "/api/jobs/claims",
      "/api/jobs/postings/:id",
      "/api/discovery",
      "/api/discovery/candidates",
      "/api/trending",
      "/api/data-audit",
      "/api/team",
      "/api/team/claims",
      "/api/products",
      "/api/products/claims",
      "/api/licenses",
      "/api/licenses/claims",
      "/api/cap-table",
      "/api/health",
    ],
  }),
);

const port = parseInt(process.env.PORT || "3000");

export { app };

export default {
  port,
  fetch: app.fetch,
};
