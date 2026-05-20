/** Mirrors GET /api/status — keep in sync with apps/api/src/routes/status.ts */

export type FreshnessLevel = "healthy" | "warning" | "stale" | "unknown";

export interface StatusCounts {
	companies: number;
	signals: number;
	events: number;
	funding: number;
	xPosts: number;
	pendingCandidates?: number;
}

export interface StatusLast24h {
	signals: number;
	events: number;
}

export interface StatusFreshness {
	lastSignalAt: string | null;
	lastEventAt: string | null;
	lastXAt: string | null;
}

export interface StatusTopSource {
	source: string;
	count: number;
}

export interface StatusRecentEvent {
	event_type: string;
	company_name: string | null;
	amount_usd: number | null;
	created_at: string;
}

export interface StatusResponse {
	counts: StatusCounts;
	last24h: StatusLast24h;
	freshness?: StatusFreshness;
	topSources: StatusTopSource[];
	recentEvents: StatusRecentEvent[];
	queriedAt?: string;
}

export interface FreshnessMetric {
	key: keyof StatusFreshness;
	label: string;
	shortLabel: string;
	at: string | null;
	level: FreshnessLevel;
	relativeLabel: string;
	absoluteLabel: string;
}

export interface IngestHealthSummary {
	/** Core RSS + events pipeline (excludes X). */
	overall: FreshnessLevel;
	pipelineOverall?: FreshnessLevel;
	metrics: FreshnessMetric[];
	apiReachable: boolean;
	queriedAt: string | null;
}
