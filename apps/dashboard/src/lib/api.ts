import type { CompanyDetailResponse } from "$lib/types/company";
import type { DataAuditResponse } from "$lib/types/dataAudit";
import type { StatusResponse } from "$lib/types/status";
import type {
	FundingClaimsResponse,
	FundingListResponse,
	FundingRoundDetailResponse,
	InvestorsListResponse,
	JobClaimsResponse,
	JobPostingDetailResponse,
	JobsListResponse,
} from "$lib/types/phase-b";

const API_BASE =
	(typeof import.meta.env !== "undefined" && import.meta.env.PUBLIC_CI_API_URL) ||
	"http://localhost:3000";

export class ApiError extends Error {
	readonly status: number;

	constructor(status: number, message: string) {
		super(message);
		this.name = "ApiError";
		this.status = status;
	}
}

export async function fetchAPI<T>(path: string): Promise<T> {
	const res = await fetch(`${API_BASE}${path}`, {
		headers: { Accept: "application/json" },
	});

	if (!res.ok) {
		let detail = `HTTP ${res.status}`;
		try {
			const body = (await res.json()) as { error?: string; message?: string };
			detail = body.error ?? body.message ?? detail;
		} catch {
			/* non-JSON error body */
		}
		throw new ApiError(res.status, detail);
	}

	return res.json() as Promise<T>;
}

export async function search(
	q: string,
	mode: "auto" | "semantic" | "keyword" = "auto",
) {
	const qs = new URLSearchParams({ q, mode });
	return fetchAPI(`/api/search?${qs}`);
}

export interface CompaniesListResponse {
	companies: Record<string, unknown>[];
	total?: number;
}

export async function getCompanies(
	sort: "name" | "score" = "name",
): Promise<CompaniesListResponse> {
	const qs = new URLSearchParams({ sort, limit: "200" });
	return fetchAPI<CompaniesListResponse>(`/api/companies?${qs}`);
}

export async function getCompany(idOrSlug: string): Promise<CompanyDetailResponse> {
	return fetchAPI<CompanyDetailResponse>(`/api/companies/${encodeURIComponent(idOrSlug)}`);
}

export interface SignalRecord {
	source: string;
	signal_label?: string;
	signal_type?: string;
	company_name?: string;
	data_json?: string;
	detected_at?: string;
}

export interface SignalsListResponse {
	signals: SignalRecord[];
	total: number;
}

export async function getSignals(params?: {
	source?: string;
	limit?: number;
}): Promise<SignalsListResponse> {
	const qs = new URLSearchParams();
	if (params?.source) qs.set("source", params.source);
	if (params?.limit != null) qs.set("limit", String(params.limit));
	const query = qs.toString();
	return fetchAPI<SignalsListResponse>(`/api/signals${query ? `?${query}` : ""}`);
}

export interface IntelligenceEventRecord {
	event_type: string;
	company_name?: string | null;
	amount_usd?: number | null;
	created_at?: string;
}

export interface EventsListResponse {
	events: IntelligenceEventRecord[];
	total?: number;
}

export async function getEvents(params?: {
	type?: string;
	limit?: number;
}): Promise<EventsListResponse> {
	const qs = new URLSearchParams();
	if (params?.type) qs.set("type", params.type);
	if (params?.limit != null) qs.set("limit", String(params.limit));
	const query = qs.toString();
	return fetchAPI<EventsListResponse>(`/api/events${query ? `?${query}` : ""}`);
}

export async function getFunding(): Promise<FundingListResponse> {
	return fetchAPI<FundingListResponse>("/api/funding");
}

export async function getFundingClaims(params?: {
	companyId?: number;
	limit?: number;
}): Promise<FundingClaimsResponse> {
	const qs = new URLSearchParams();
	if (params?.companyId != null) qs.set("company_id", String(params.companyId));
	if (params?.limit != null) qs.set("limit", String(params.limit));
	const query = qs.toString();
	return fetchAPI<FundingClaimsResponse>(`/api/funding/claims${query ? `?${query}` : ""}`);
}

export async function getFundingRound(id: number | string): Promise<FundingRoundDetailResponse> {
	return fetchAPI<FundingRoundDetailResponse>(`/api/funding/rounds/${id}`);
}

export async function getFundingInvestors(params?: {
	limit?: number;
	tier?: number;
}): Promise<InvestorsListResponse> {
	const qs = new URLSearchParams();
	if (params?.limit != null) qs.set("limit", String(params.limit));
	if (params?.tier != null) qs.set("tier", String(params.tier));
	const query = qs.toString();
	return fetchAPI<InvestorsListResponse>(`/api/funding/investors${query ? `?${query}` : ""}`);
}

export async function getJobs(params?: {
	limit?: number;
	active?: boolean;
}): Promise<JobsListResponse> {
	const qs = new URLSearchParams();
	if (params?.limit != null) qs.set("limit", String(params.limit));
	if (params?.active != null) qs.set("active", params.active ? "true" : "false");
	const query = qs.toString();
	return fetchAPI<JobsListResponse>(`/api/jobs${query ? `?${query}` : ""}`);
}

export async function getJobClaims(params?: {
	companyId?: number;
	limit?: number;
}): Promise<JobClaimsResponse> {
	const qs = new URLSearchParams();
	if (params?.companyId != null) qs.set("company_id", String(params.companyId));
	if (params?.limit != null) qs.set("limit", String(params.limit));
	const query = qs.toString();
	return fetchAPI<JobClaimsResponse>(`/api/jobs/claims${query ? `?${query}` : ""}`);
}

export async function getJobPosting(id: number | string): Promise<JobPostingDetailResponse> {
	return fetchAPI<JobPostingDetailResponse>(`/api/jobs/postings/${id}`);
}

export async function getJobsForCompany(companyId: number | string) {
	return fetchAPI(`/api/jobs/company/${companyId}`);
}

export async function getDataAudit(): Promise<DataAuditResponse> {
	return fetchAPI<DataAuditResponse>("/api/data-audit");
}

export async function getStatus(): Promise<StatusResponse> {
	const status = await fetchAPI<StatusResponse>("/api/status");
	return {
		...status,
		queriedAt: status.queriedAt ?? new Date().toISOString(),
	};
}

export function getApiBaseUrl(): string {
	return API_BASE;
}
