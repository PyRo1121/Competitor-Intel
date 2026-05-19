import { Hono } from "hono";
import { cors } from "hono/cors";
import { logger } from "hono/logger";
import { secureHeaders } from "hono/secure-headers";
import { timing } from "hono/timing";
import companies from "./routes/companies";
import signals from "./routes/signals";
import events from "./routes/events";
import funding from "./routes/funding";
import status from "./routes/status";
import search from "./routes/search";
import trending from "./routes/trending";
import competitors from "./routes/competitors";
import scoring from "./routes/scoring";
import alerts from "./routes/alerts";
import jobs from "./routes/jobs";
import discovery from "./routes/discovery";

const app = new Hono();

app.use("*", cors());
app.use("*", logger());
app.use("*", secureHeaders());
app.use("*", timing());

app.onError((err, c) => {
  console.error(err);
  return c.json({ error: "Internal Server Error" }, 500);
});

app.notFound((c) => c.json({ error: "Not Found" }, 404));

app.get("/health", (c) => c.json({ status: "ok", timestamp: new Date().toISOString() }));

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

app.get("/", (c) =>
  c.json({
    name: "Competitor Intelligence API",
    version: "2.0.0",
    endpoints: [
      "/api/companies",
      "/api/signals",
      "/api/events",
      "/api/funding",
      "/api/status",
      "/api/search",
      "/api/competitors",
      "/api/scoring",
      "/api/alerts",
      "/api/jobs",
      "/api/discovery",
      "/api/trending",
      "/api/health",
    ],
  })
);

const port = parseInt(process.env.PORT || "3000");

export default {
  port,
  fetch: app.fetch,
};
