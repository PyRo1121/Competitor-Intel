/** Display helpers for money, scores, and labels. */

export function formatUsd(
  amount: number | null | undefined,
  opts?: { compact?: boolean; undisclosed?: string },
): string {
  if (amount == null || Number.isNaN(amount)) {
    return opts?.undisclosed ?? "Undisclosed";
  }

  const compact = opts?.compact !== false;
  const abs = Math.abs(amount);
  const sign = amount < 0 ? "-" : "";

  if (!compact) {
    return `${sign}$${amount.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  }

  if (abs >= 1_000_000_000) {
    return `${sign}$${(abs / 1_000_000_000).toFixed(2)}B`;
  }
  if (abs >= 1_000_000) {
    return `${sign}$${(abs / 1_000_000).toFixed(1)}M`;
  }
  if (abs >= 1_000) {
    return `${sign}$${(abs / 1_000).toFixed(0)}K`;
  }
  return `${sign}$${abs.toLocaleString()}`;
}

export function formatPercent(
  fraction: number | null | undefined,
  fractionIsZeroToOne = true,
): string {
  if (fraction == null || Number.isNaN(fraction)) return "—";
  const pct = fractionIsZeroToOne ? fraction * 100 : fraction;
  return `${Math.round(pct)}%`;
}

export function formatSourceTier(tier: string | null | undefined): string {
  if (!tier) return "Unknown";
  return tier.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function formatSeniority(band: string | null | undefined): string {
  if (!band) return "—";
  return band.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function truncate(text: string | null | undefined, max = 120): string {
  if (!text) return "";
  const t = text.trim();
  if (t.length <= max) return t;
  return `${t.slice(0, max - 1)}…`;
}
