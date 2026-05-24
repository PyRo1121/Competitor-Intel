export interface ProfileClaimRow {
  id: number;
  field_key: string;
  field_value: string;
  source?: string | null;
  source_url?: string | null;
  source_tier?: string | null;
  source_weight?: number | null;
  extraction_confidence?: number | null;
  extracted_at?: string | null;
}

export interface TeamClaimRow {
  id: number;
  name: string;
  role?: string | null;
  source?: string | null;
  source_url?: string | null;
  source_tier?: string | null;
  corroboration_score?: number | null;
}

export interface CompanyProfileClaimsResponse {
  company_id: number;
  profile_claims: ProfileClaimRow[];
  team_claims: TeamClaimRow[];
  product_claims: Record<string, unknown>[];
  license_claims: Record<string, unknown>[];
}
