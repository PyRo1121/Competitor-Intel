import { timingSafeEqual } from "crypto";
import type { Context, Next } from "hono";

function timingSafeStringEqual(a: string, b: string): boolean {
  const enc = new TextEncoder();
  const ab = enc.encode(a);
  const bb = enc.encode(b);
  if (ab.length !== bb.length) {
    return false;
  }
  return timingSafeEqual(ab, bb);
}

function extractApiKey(c: Context): string | undefined {
  const auth = c.req.header("Authorization");
  if (auth?.startsWith("Bearer ")) {
    return auth.slice("Bearer ".length).trim();
  }
  const header = c.req.header("X-API-Key");
  return header?.trim() || undefined;
}

/** Require CI_API_KEY for mutating routes; mutations disabled when unset. */
export function requireApiKey() {
  return async (c: Context, next: Next) => {
    const expected = process.env.CI_API_KEY?.trim();
    if (!expected) {
      return c.json({ error: "Mutations disabled: set CI_API_KEY on the API server" }, 503);
    }
    const provided = extractApiKey(c);
    if (!provided || !timingSafeStringEqual(provided, expected)) {
      return c.json({ error: "Unauthorized" }, 401);
    }
    await next();
  };
}
