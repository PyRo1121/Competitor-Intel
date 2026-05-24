/**
 * Private-company trust model: confidence rises as independent sources and repetition
 * increase (press, careers, company posts, etc.) — not a public-filing verified/unverified split.
 *
 * Backend: funding_rounds.corroboration_score (0–1) from claim diversity, volume,
 * official company sources, and field agreement — see funding_aggregator.compute_corroboration.
 */

export type ConfidenceLabel = "Early signal" | "Building" | "Strong";

/** Map 0–1 score to a short human label for per-item tags. */
export function confidenceLabel(score: number | null | undefined): ConfidenceLabel {
  if (score == null) return "Early signal";
  if (score >= 0.75) return "Strong";
  if (score >= 0.45) return "Building";
  return "Early signal";
}

/** Same thresholds as confidenceLabel — for events / classifier confidence fields. */
export function eventConfidenceLabel(confidence: number | null | undefined): ConfidenceLabel {
  return confidenceLabel(confidence);
}

export function corroborationLabel(score: number | null | undefined): ConfidenceLabel {
  return confidenceLabel(score);
}

export function confidencePercent(score: number | null | undefined): string {
  if (score == null) return "—";
  return `${Math.round(score * 100)}%`;
}
