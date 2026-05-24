/**
 * Canonical map of what the dashboard shows → DB tables → collectors → trust tier.
 * Row counts are filled at request time in routes/dataAudit.ts.
 */

export type TrustTier =
  | "verified"
  | "corroborated"
  | "operational"
  | "partial"
  | "empty"
  | "inferred";

export type PipelineStatus = "active" | "partial" | "not_wired" | "deprecated";

export interface DataDomainDefinition {
  id: string;
  name: string;
  tier: TrustTier;
  table: string;
  collector: string | null;
  pipelineStatus: PipelineStatus;
  dashboardSurfaces: string[];
  guidance: string;
  keyColumns: string[];
  /** SQL: single number, first column = count. Use ? for company_id scope where needed. */
  countSql: string;
  /** SQL: companies with at least one row. Omit to use countSql only. */
  companiesWithDataSql?: string;
}

export const TRUST_TIER_LABELS: Record<TrustTier, { label: string; description: string }> = {
  verified: {
    label: "Verified",
    description:
      "Rare for private cos: high corroboration plus official or filing-grade sources when present.",
  },
  corroborated: {
    label: "Corroborated",
    description:
      "Confidence-scored merge (e.g. funding); score increases as independent source noise grows.",
  },
  operational: {
    label: "Operational",
    description: "Raw ingest + NLP classification; useful for monitoring, not ground truth.",
  },
  partial: {
    label: "Partial",
    description: "Collector runs but low company coverage or sparse fields.",
  },
  empty: {
    label: "Not collected",
    description: "Schema exists; no pipeline writing rows (or table unused).",
  },
  inferred: {
    label: "Inferred",
    description: "Derived from other signals (jobs, GitHub, heuristics); confidence varies.",
  },
};

export const DATA_DOMAINS: DataDomainDefinition[] = [
  {
    id: "companies",
    name: "Company registry",
    tier: "operational",
    table: "companies",
    collector: "seed / manual + discovery",
    pipelineStatus: "active",
    dashboardSurfaces: ["Companies list", "Company header", "Search"],
    guidance:
      "Curated watchlist. Slug, website, X, GitHub org are operator-maintained — verify before trusting identity.",
    keyColumns: ["name", "slug", "website", "x_handle", "github_org", "industry", "status"],
    countSql: "SELECT COUNT(*) FROM companies",
  },
  {
    id: "company_details",
    name: "Company enrichment (HQ, team size, description)",
    tier: "partial",
    table: "company_details",
    collector: "collectors/enrichment/company_enricher.py",
    pipelineStatus: "partial",
    dashboardSurfaces: ["Company overview (sparse)"],
    guidance:
      "Only a handful of companies enriched. Crunchbase/website scrape — not registry filings.",
    keyColumns: ["founded_year", "headquarters", "team_size", "business_model", "description_long"],
    countSql: "SELECT COUNT(*) FROM company_details",
    companiesWithDataSql: "SELECT COUNT(DISTINCT company_id) FROM company_details",
  },
  {
    id: "team_members",
    name: "Leadership & officers (CEO, directors)",
    tier: "partial",
    table: "team_members",
    collector: "collectors/company_data_rollup.py",
    pipelineStatus: "partial",
    dashboardSurfaces: [
      "Company → Team tab",
      "Jobs → recent hires",
      "Scoring → founder_team_quality",
    ],
    guidance:
      "From team_member_claims (press/SEC/YC). Run make company-data-rollup. Scoring uses corroboration_score ≥ 0.35 only.",
    keyColumns: ["name", "role", "is_founder", "joined_date", "source", "linkedin_url"],
    countSql: "SELECT COUNT(*) FROM team_members",
    companiesWithDataSql: "SELECT COUNT(DISTINCT company_id) FROM team_members",
  },
  {
    id: "funding_rounds",
    name: "Canonical funding rounds",
    tier: "corroborated",
    table: "funding_rounds",
    collector: "collectors/funding_rollup.py + signal_processor",
    pipelineStatus: "active",
    dashboardSurfaces: ["Funding", "Company → Funding", "Dashboard KPIs"],
    guidance:
      "corroboration_score rises with independent sources and agreement — primary trust signal for private companies, not filing verification.",
    keyColumns: [
      "round_type",
      "amount_usd",
      "lead_investor",
      "announced_date",
      "corroboration_score",
      "official_report_count",
    ],
    countSql: "SELECT COUNT(*) FROM funding_rounds",
    companiesWithDataSql: "SELECT COUNT(DISTINCT company_id) FROM funding_rounds",
  },
  {
    id: "funding_claims",
    name: "Funding claims (per source)",
    tier: "operational",
    table: "funding_round_claims",
    collector: "funding_collector + big_deals + RSS/press fanout",
    pipelineStatus: "active",
    dashboardSurfaces: ["Funding → claims layer"],
    guidance: "Source-of-truth observations before merge. Always trace source_url and source_tier.",
    keyColumns: ["round_type", "amount_usd", "source", "source_tier", "is_official", "headline"],
    countSql: "SELECT COUNT(*) FROM funding_round_claims",
    companiesWithDataSql: "SELECT COUNT(DISTINCT company_id) FROM funding_round_claims",
  },
  {
    id: "investor_firms",
    name: "Investor firms",
    tier: "corroborated",
    table: "investor_firms",
    collector: "collectors/investor_collector.py",
    pipelineStatus: "partial",
    dashboardSurfaces: ["Funding → investors", "Round detail participants"],
    guidance: "Normalized names from funding extraction; tier is heuristic.",
    keyColumns: ["name", "investor_type", "tier", "website"],
    countSql: "SELECT COUNT(*) FROM investor_firms",
  },
  {
    id: "job_postings",
    name: "Job postings (ATS)",
    tier: "operational",
    table: "job_postings",
    collector: "collectors/job_tracker.py + job_pipeline",
    pipelineStatus: "active",
    dashboardSurfaces: ["Jobs", "Company → Jobs", "Hiring pulse"],
    guidance:
      "Hiring demand from Greenhouse/Lever/etc. Not leadership roster. Filter template titles.",
    keyColumns: ["title", "department", "location", "seniority_band", "source", "is_active"],
    countSql:
      "SELECT COUNT(*) FROM job_postings WHERE is_active = 1 AND LOWER(title) NOT LIKE '%template%'",
    companiesWithDataSql:
      "SELECT COUNT(DISTINCT company_id) FROM job_postings WHERE is_active = 1 AND LOWER(title) NOT LIKE '%template%'",
  },
  {
    id: "raw_signals",
    name: "Raw signals (RSS, X, GitHub, …)",
    tier: "operational",
    table: "raw_signals",
    collector: "PARALLEL_COLLECTORS (rss, x, github_signals, …)",
    pipelineStatus: "active",
    dashboardSurfaces: ["Signals", "Company → Signals feed"],
    guidance:
      "Unprocessed payloads. Company linkage can be wrong or missing — check data_json source.",
    keyColumns: ["source", "signal_type", "data_json", "detected_at", "company_id"],
    countSql: "SELECT COUNT(*) FROM raw_signals",
    companiesWithDataSql:
      "SELECT COUNT(DISTINCT company_id) FROM raw_signals WHERE company_id IS NOT NULL",
  },
  {
    id: "intelligence_events",
    name: "Intelligence events (classified)",
    tier: "operational",
    table: "intelligence_events",
    collector: "collectors/signal_processor.py",
    pipelineStatus: "active",
    dashboardSurfaces: ["Events", "Company → Recent intelligence"],
    guidance:
      "NLP/heuristic labels (Funding Round, Hiring, etc.). Amounts and investors may be extracted wrong.",
    keyColumns: [
      "event_type",
      "amount_usd",
      "lead_investor",
      "confidence",
      "source",
      "description",
    ],
    countSql: "SELECT COUNT(*) FROM intelligence_events",
    companiesWithDataSql:
      "SELECT COUNT(DISTINCT company_id) FROM intelligence_events WHERE company_id IS NOT NULL",
  },
  {
    id: "github_metrics",
    name: "GitHub metrics",
    tier: "partial",
    table: "github_metrics",
    collector: "collectors/github_collector.py",
    pipelineStatus: "partial",
    dashboardSurfaces: ["Company → GitHub panel"],
    guidance: "Only companies with github_org and successful collector run.",
    keyColumns: ["total_commits", "contributor_count", "primary_language", "star_growth_30d"],
    countSql: "SELECT COUNT(*) FROM github_metrics",
    companiesWithDataSql: "SELECT COUNT(DISTINCT company_id) FROM github_metrics",
  },
  {
    id: "technology_stack",
    name: "Technology stack",
    tier: "inferred",
    table: "technology_stack",
    collector: "collectors/tech_stack_detector.py",
    pipelineStatus: "active",
    dashboardSurfaces: ["Company → Tech tab"],
    guidance: "Inferred from job postings and GitHub — not a Wappalyzer crawl of production.",
    keyColumns: ["category", "technology", "confidence", "detection_source"],
    countSql: "SELECT COUNT(*) FROM technology_stack",
    companiesWithDataSql: "SELECT COUNT(DISTINCT company_id) FROM technology_stack",
  },
  {
    id: "competitor_relationships",
    name: "Competitor graph",
    tier: "inferred",
    table: "competitor_relationships",
    collector: "collectors/competitor_mapper.py",
    pipelineStatus: "partial",
    dashboardSurfaces: ["Company → Competitive set"],
    guidance: "Auto-detected overlaps; very low coverage. Treat as suggestions.",
    keyColumns: ["competitor_id", "relationship_type", "overlap_areas", "confidence"],
    countSql: "SELECT COUNT(*) FROM competitor_relationships",
    companiesWithDataSql: "SELECT COUNT(DISTINCT company_id) FROM competitor_relationships",
  },
  {
    id: "products",
    name: "Products catalog",
    tier: "empty",
    table: "products",
    collector: null,
    pipelineStatus: "not_wired",
    dashboardSurfaces: ["Company summary (products count)"],
    guidance: "Table unused.",
    keyColumns: ["name", "description", "category", "pricing_json"],
    countSql: "SELECT COUNT(*) FROM products",
    companiesWithDataSql: "SELECT COUNT(DISTINCT company_id) FROM products",
  },
  {
    id: "x_posts",
    name: "X posts archive",
    tier: "partial",
    table: "x_posts",
    collector: "collectors/x_signal_collector.py",
    pipelineStatus: "partial",
    dashboardSurfaces: ["(not on main dashboard — signals use raw_signals)"],
    guidance: "Sparse; most X content lives in raw_signals.",
    keyColumns: ["text", "posted_at", "likes", "sentiment"],
    countSql: "SELECT COUNT(*) FROM x_posts",
    companiesWithDataSql: "SELECT COUNT(DISTINCT company_id) FROM x_posts",
  },
  {
    id: "website_snapshots",
    name: "Website change detection",
    tier: "operational",
    table: "website_snapshots",
    collector: "collectors/website_monitor.py",
    pipelineStatus: "partial",
    dashboardSurfaces: ["(internal / alerts)"],
    guidance: "Homepage hash diffs; not shown on company page yet.",
    keyColumns: ["url", "hash", "captured_at"],
    countSql: "SELECT COUNT(*) FROM website_snapshots",
    companiesWithDataSql: "SELECT COUNT(DISTINCT company_id) FROM website_snapshots",
  },
];

export const DASHBOARD_SURFACE_AUDIT: {
  surface: string;
  path: string;
  domains: string[];
  notes: string;
}[] = [
  {
    surface: "Dashboard home",
    path: "/",
    domains: ["companies", "funding_rounds", "job_postings", "raw_signals"],
    notes:
      "Aggregate counts; funding dollar KPIs only when corroboration meets display threshold (no split sections).",
  },
  {
    surface: "Companies list",
    path: "/companies",
    domains: ["companies"],
    notes: "Identity fields only.",
  },
  {
    surface: "Company dossier",
    path: "/companies/:slug",
    domains: [
      "companies",
      "company_details",
      "team_members",
      "funding_rounds",
      "job_postings",
      "raw_signals",
      "intelligence_events",
      "github_metrics",
      "technology_stack",
      "competitor_relationships",
    ],
    notes: "Highest risk surface — mixed trust tiers on one page.",
  },
  {
    surface: "Signals",
    path: "/signals",
    domains: ["raw_signals"],
    notes: "Show source + detected_at; never imply verification.",
  },
  {
    surface: "Events",
    path: "/events",
    domains: ["intelligence_events"],
    notes: "Event_type is classifier output, not legal fact.",
  },
  {
    surface: "Funding",
    path: "/funding",
    domains: ["funding_rounds", "funding_claims", "investor_firms"],
    notes: "Corroboration badges are mandatory reading.",
  },
  {
    surface: "Jobs",
    path: "/jobs",
    domains: ["job_postings"],
    notes: "ATS listings; corroboration on merged postings after job rollup.",
  },
  {
    surface: "Search",
    path: "/search",
    domains: ["companies", "raw_signals"],
    notes: "Semantic/keyword over ingested corpus.",
  },
  {
    surface: "Settings",
    path: "/settings",
    domains: ["raw_signals"],
    notes: "Ingest freshness only.",
  },
];
