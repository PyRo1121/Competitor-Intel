export interface CompanyValuation {
  valuation_usd: number;
  valuation_kind: "reported" | "estimated";
  method: string;
  confidence: number;
  as_of_date?: string | null;
  updated_at?: string | null;
}

export interface CompanySummary {
  signals: number;
  events: number;
  active_jobs: number;
  funding_rounds: number;
  total_raised_usd: number;
  /** Sum of rounds with corroboration_score >= 0.45 (optional KPI / analytics). */
  verified_raised_usd?: number;
  max_funding_corroboration?: number | null;
  funding_official_reports?: number;
  team_size: number;
  products: number;
  licenses?: number;
}

export interface CompanyRecord {
  id: number;
  name: string;
  slug: string;
  website?: string | null;
  x_handle?: string | null;
  github_org?: string | null;
  industry?: string | null;
  status: string;
  description?: string | null;
  github_stars?: number | null;
  notes?: string | null;
}

export interface CompanyDetailResponse {
  company: CompanyRecord;
  details?: Record<string, unknown> | null;
  valuation?: CompanyValuation | null;
  funding: Record<string, unknown>[];
  products: Record<string, unknown>[];
  team: Record<string, unknown>[];
  licenses?: Record<string, unknown>[];
  license_claims?: Record<string, unknown>[];
  cap_table?: Record<string, unknown>[];
  github?: Record<string, unknown> | null;
  tech_stack: { category?: string; technology: string; confidence: number }[];
  competitors: Record<string, unknown>[];
  summary: CompanySummary;
  recent_signals: Record<string, unknown>[];
  recent_events: Record<string, unknown>[];
}

export interface CompanyJobsResponse {
  company: string;
  company_id: number;
  company_slug: string;
  jobs: Record<string, unknown>[];
  stats?: Record<string, unknown>;
  skill_mix?: { skill: string; category?: string; mention_count: number }[];
  job_boards?: Record<string, unknown>[];
  recent_hires?: { name: string; role?: string; joined_date?: string }[];
}
