export type TrustTier =
  | "verified"
  | "corroborated"
  | "operational"
  | "partial"
  | "empty"
  | "inferred";

export interface DataAuditDomain {
  id: string;
  name: string;
  tier: TrustTier;
  table: string;
  collector: string | null;
  pipelineStatus: string;
  dashboardSurfaces: string[];
  guidance: string;
  keyColumns: string[];
  rowCount: number;
  companiesWithData: number;
  totalCompanies: number;
  coveragePct: number;
  fundingVerified?: number;
  fundingUnverified?: number;
}

export interface DataAuditResponse {
  auditedAt: string;
  totalCompanies: number;
  trustTiers: Record<TrustTier, { label: string; description: string }>;
  byTier: { tier: TrustTier; label: string; description: string; domainCount: number }[];
  domains: DataAuditDomain[];
  dashboardSurfaces: {
    surface: string;
    path: string;
    domains: string[];
    notes: string;
  }[];
  highlights: {
    leadershipEmpty: boolean;
    productsEmpty: boolean;
    fundingLowCorroboration?: DataAuditDomain & {
      fundingVerified?: number;
      fundingUnverified?: number;
    };
    enrichmentCoveragePct: number;
    githubCoveragePct: number;
  };
  recommendations: string[];
}
