/**
 * Ingest freshness thresholds — aligned with docs/SCHEDULING.md
 * (hourly RSS tier, ~5×/day Grok X, daily heavy pipeline).
 */

import type {
  FreshnessLevel,
  FreshnessMetric,
  IngestHealthSummary,
  StatusFreshness,
  StatusResponse,
} from "$lib/types/status";

const DISPLAY_TZ = "America/New_York";

/** Max age (ms) before status escalates warning → stale */
const THRESHOLDS_MS = {
  signals: { healthy: 2 * 60 * 60 * 1000, warning: 6 * 60 * 60 * 1000 },
  events: { healthy: 3 * 60 * 60 * 1000, warning: 12 * 60 * 60 * 1000 },
  x: { healthy: 5 * 60 * 60 * 1000, warning: 10 * 60 * 60 * 1000 },
} as const;

const LEVEL_RANK: Record<FreshnessLevel, number> = {
  healthy: 0,
  unknown: 1,
  warning: 2,
  stale: 3,
};

const rtf = new Intl.RelativeTimeFormat("en-US", { numeric: "auto" });

export function parseTimestamp(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const ms = Date.parse(iso);
  return Number.isNaN(ms) ? null : new Date(ms);
}

export function assessFreshness(
  at: string | null,
  kind: keyof typeof THRESHOLDS_MS,
  now: Date = new Date(),
): FreshnessLevel {
  const date = parseTimestamp(at);
  if (!date) return "unknown";

  const ageMs = now.getTime() - date.getTime();
  if (ageMs < 0) return "healthy";

  const { healthy, warning } = THRESHOLDS_MS[kind];
  if (ageMs <= healthy) return "healthy";
  if (ageMs <= warning) return "warning";
  return "stale";
}

export function formatRelativeTime(at: string | null, now: Date = new Date()): string {
  const date = parseTimestamp(at);
  if (!date) return "No data yet";

  const diffSec = Math.round((date.getTime() - now.getTime()) / 1000);
  const abs = Math.abs(diffSec);

  if (abs < 45) return "just now";

  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ["year", 60 * 60 * 24 * 365],
    ["month", 60 * 60 * 24 * 30],
    ["day", 60 * 60 * 24],
    ["hour", 60 * 60],
    ["minute", 60],
  ];

  for (const [unit, seconds] of units) {
    if (abs >= seconds || unit === "minute") {
      const value = Math.round(diffSec / seconds);
      return rtf.format(value, unit);
    }
  }

  return rtf.format(diffSec, "second");
}

export function formatAbsoluteTime(at: string | null): string {
  const date = parseTimestamp(at);
  if (!date) return "—";

  // dateStyle/timeStyle cannot be combined with timeZoneName (throws in browsers).
  return new Intl.DateTimeFormat("en-US", {
    timeZone: DISPLAY_TZ,
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function worstLevel(levels: FreshnessLevel[]): FreshnessLevel {
  return levels.reduce((worst, level) => (LEVEL_RANK[level] > LEVEL_RANK[worst] ? level : worst));
}

export function buildIngestHealth(
  status: StatusResponse | null,
  apiReachable: boolean,
): IngestHealthSummary {
  if (!status) {
    return {
      overall: "unknown",
      metrics: [],
      apiReachable,
      queriedAt: null,
    };
  }

  const now = new Date();
  const freshness: StatusFreshness = status.freshness ?? {
    lastSignalAt: null,
    lastEventAt: null,
    lastXAt: null,
  };

  const specs: {
    key: keyof StatusFreshness;
    label: string;
    shortLabel: string;
    kind: keyof typeof THRESHOLDS_MS;
  }[] = [
    {
      key: "lastSignalAt",
      label: "Signals (RSS & open web)",
      shortLabel: "Signals",
      kind: "signals",
    },
    { key: "lastEventAt", label: "Intelligence events", shortLabel: "Events", kind: "events" },
    { key: "lastXAt", label: "X / Grok verification", shortLabel: "X", kind: "x" },
  ];

  const metrics: FreshnessMetric[] = specs.map(({ key, label, shortLabel, kind }) => {
    const at = freshness[key];
    const level = assessFreshness(at, kind, now);
    return {
      key,
      label,
      shortLabel,
      at,
      level,
      relativeLabel: formatRelativeTime(at, now),
      absoluteLabel: formatAbsoluteTime(at),
    };
  });

  // Pipeline ingest badge: RSS + events only. X is auxiliary and must not mark core ingest stale.
  const pipelineMetrics = metrics.filter((m) => m.key !== "lastXAt");
  const pipelineOverall = worstLevel(pipelineMetrics.map((m) => m.level));

  return {
    overall: pipelineOverall,
    pipelineOverall,
    metrics,
    apiReachable,
    queriedAt: status.queriedAt ?? null,
  };
}

export function levelTone(level: FreshnessLevel): {
  dot: string;
  text: string;
  border: string;
  bg: string;
  label: string;
} {
  switch (level) {
    case "healthy":
      return {
        dot: "bg-[var(--color-healthy)]",
        text: "text-[var(--color-healthy)]",
        border: "border-[var(--color-healthy)]/25",
        bg: "bg-[rgba(61,214,140,0.08)]",
        label: "Fresh",
      };
    case "warning":
      return {
        dot: "bg-[var(--color-warning)]",
        text: "text-[var(--color-warning)]",
        border: "border-[var(--color-warning)]/25",
        bg: "bg-[rgba(240,180,41,0.08)]",
        label: "Aging",
      };
    case "stale":
      return {
        dot: "bg-[var(--color-stale)]",
        text: "text-[var(--color-stale)]",
        border: "border-[var(--color-stale)]/25",
        bg: "bg-[rgba(240,113,120,0.08)]",
        label: "Stale",
      };
    default:
      return {
        dot: "bg-[var(--color-ink-faint)]",
        text: "text-[var(--color-ink-muted)]",
        border: "border-[var(--color-border)]",
        bg: "bg-[var(--color-surface-hover)]",
        label: "Unknown",
      };
  }
}

export function formatEventType(type: string): string {
  return type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function parseSignalPreview(dataJson: string | null | undefined): string {
  if (!dataJson) return "No preview available";

  try {
    const data = JSON.parse(dataJson) as {
      title?: string;
      description?: string;
      name?: string;
    };
    if (typeof data.title === "string" && data.title.trim()) return data.title.trim();
    if (typeof data.name === "string" && data.name.trim()) return data.name.trim();
    if (typeof data.description === "string" && data.description.trim()) {
      return data.description.trim().slice(0, 240);
    }
  } catch {
    return dataJson.slice(0, 240);
  }

  return "No preview available";
}
