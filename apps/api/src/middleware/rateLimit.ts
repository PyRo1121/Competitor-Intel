/**
 * In-memory per-IP rate limit for single-node bare-metal API.
 */
import type { MiddlewareHandler } from "hono";

const WINDOW_MS = 60_000;
const MAX_BUCKETS = 10_000;

function maxPerWindow(): number {
  const raw = process.env.CI_API_RATE_LIMIT_RPM ?? "300";
  const n = Number.parseInt(raw, 10);
  return Number.isFinite(n) && n > 0 ? n : 300;
}

type Bucket = { count: number; resetAt: number };

const buckets = new Map<string, Bucket>();

function clientKey(req: Request): string {
  const forwarded = req.headers.get("x-forwarded-for");
  if (forwarded) {
    return forwarded.split(",")[0]?.trim() || "unknown";
  }
  return req.headers.get("x-real-ip") ?? "local";
}

function pruneBuckets(now: number): void {
  if (buckets.size <= MAX_BUCKETS) {
    return;
  }
  for (const [key, bucket] of buckets) {
    if (now >= bucket.resetAt) {
      buckets.delete(key);
    }
  }
  if (buckets.size <= MAX_BUCKETS) {
    return;
  }
  const drop = buckets.size - MAX_BUCKETS;
  let n = 0;
  for (const key of buckets.keys()) {
    buckets.delete(key);
    n += 1;
    if (n >= drop) {
      break;
    }
  }
}

export function rateLimit(): MiddlewareHandler {
  return async (c, next) => {
    const path = new URL(c.req.url).pathname;
    if (path === "/health") {
      return next();
    }

    const limit = maxPerWindow();
    const key = clientKey(c.req.raw);
    const now = Date.now();
    pruneBuckets(now);

    let bucket = buckets.get(key);
    if (!bucket || now >= bucket.resetAt) {
      bucket = { count: 0, resetAt: now + WINDOW_MS };
      buckets.set(key, bucket);
    }
    bucket.count += 1;
    if (bucket.count > limit) {
      const retryAfter = Math.max(1, Math.ceil((bucket.resetAt - now) / 1000));
      c.header("Retry-After", String(retryAfter));
      return c.json({ error: "Too Many Requests", limit, window_seconds: WINDOW_MS / 1000 }, 429);
    }
    return next();
  };
}
