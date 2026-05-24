/** API shapes for funding, jobs, and company-entity list endpoints. */

export interface FundingStats {
  total_rounds: number;
  total_raised: number | null;
  avg_round: number | null;
  companies_funded: number;
  total_claims: number;
  total_round_participants: number;
  total_attributions: number;
  investor_firms: number;
}

export interface FundingRoundRow {
  id: number;
  company_id: number;
  company_name: string | null;
  round_type: string | null;
  amount_usd: number | null;
  announced_date: string | null;
  lead_investor: string | null;
  corroboration_score: number | null;
  report_count: number | null;
  official_report_count?: number | null;
  claim_count?: number;
  participant_count?: number;
  instrument_type?: string | null;
}

export interface FundingListResponse {
  funding: FundingRoundRow[];
  stats: FundingStats;
}

export interface FundingClaimParticipant {
  id: number;
  investor_name?: string | null;
  investor_tier?: number | null;
  is_lead?: number | boolean;
  role?: string | null;
}

export interface FundingClaimRow {
  id: number;
  company_id: number;
  company_name: string;
  source_url: string;
  source_tier?: string | null;
  source_weight?: number | null;
  is_official?: number | boolean;
  headline?: string | null;
  snippet?: string | null;
  amount_usd?: number | null;
  round_type?: string | null;
  instrument_type?: string | null;
  participant_count?: number;
  participants: FundingClaimParticipant[];
  extracted_at?: string | null;
}

export interface FundingClaimsResponse {
  claims: FundingClaimRow[];
}

export interface RoundParticipantRow {
  id: number;
  investor_name: string | null;
  investor_tier?: number | null;
  is_lead?: number | boolean;
  corroboration_score?: number | null;
  source_attributions?: unknown[];
}

export interface FundingRoundDetailResponse {
  round: FundingRoundRow & {
    fields_provenance?: Record<string, unknown>;
    company_website?: string | null;
  };
  claims: FundingClaimRow[];
  participants: RoundParticipantRow[];
}

export interface InvestorFirmRow {
  id: number;
  name: string;
  name_normalized?: string | null;
  tier?: number | null;
  investor_type?: string | null;
  round_count?: number;
  claim_mention_count?: number;
}

export interface InvestorsListResponse {
  investors: InvestorFirmRow[];
}

export interface JobStats {
  total_postings: number;
  active_postings: number;
  total_claims: number;
  total_skills: number;
  verified_boards: number;
}

export interface JobPostingRow {
  id: number;
  company_id: number;
  company_name: string;
  company_slug?: string | null;
  title: string;
  location?: string | null;
  seniority_band?: string | null;
  employment_type?: string | null;
  remote_policy?: string | null;
  salary_min_usd?: number | null;
  salary_max_usd?: number | null;
  corroboration_score?: number | null;
  report_count?: number | null;
  skill_count?: number;
  posted_at?: string | null;
  is_active?: number | boolean;
  ats_platform?: string | null;
}

export interface JobsListResponse {
  jobs: JobPostingRow[];
  stats?: JobStats;
  count: number;
}

export interface JobSkillRow {
  skill: string;
  mention_count?: number;
}

export interface JobClaimRow {
  id: number;
  company_id: number;
  company_name: string;
  source_url: string;
  title?: string | null;
  ats_platform?: string | null;
  source_tier?: string | null;
  seniority_band?: string | null;
  remote_policy?: string | null;
  salary_min_usd?: number | null;
  salary_max_usd?: number | null;
  skill_count?: number;
  skills: JobSkillRow[];
}

export interface JobClaimsResponse {
  claims: JobClaimRow[];
}

export interface JobPostingDetailResponse {
  posting: JobPostingRow & { fields_provenance?: Record<string, unknown> };
  claims: JobClaimRow[];
  skills: JobSkillRow[];
}
