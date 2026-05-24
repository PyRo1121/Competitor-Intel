<script lang="ts">
	import { goto } from "$app/navigation";
	import { page } from "$app/stores";
	import { createQuery } from "@tanstack/svelte-query";
	import { getCompany, getCompanyProfileClaims, getJobsForCompany } from "$lib/api";
	import type { CompanyProfileClaimsResponse } from "$lib/types/profileClaims";
	import { formatUsd, formatSeniority, truncate } from "$lib/format";
	import { parseSignalPreview, formatEventType } from "$lib/freshness";
	import type { CompanyDetailResponse, CompanyJobsResponse } from "$lib/types/company";
	import CorroborationBadge from "$lib/components/CorroborationBadge.svelte";
	import SourceTag from "$lib/components/SourceTag.svelte";
	import { confidencePercent, confidenceLabel, eventConfidenceLabel } from "$lib/provenance";
	import {
		ArrowLeft,
		ExternalLink,
		GitBranch,
		Radio,
		Activity,
		Briefcase,
		Wallet,
		Users,
		Box,
		Package,
		Scale,
		Shield,
	} from "lucide-svelte";

	const slug = $derived($page.params.slug ?? "");
	type TabId =
		| "overview"
		| "signals"
		| "funding"
		| "cap_table"
		| "jobs"
		| "team"
		| "products"
		| "licenses"
		| "tech";
	let activeTab = $state<TabId>("overview");

	const tabIds: TabId[] = [
		"overview",
		"signals",
		"funding",
		"cap_table",
		"jobs",
		"team",
		"products",
		"licenses",
		"tech",
	];

	$effect(() => {
		const hash = $page.url.hash.replace(/^#/, "");
		if (hash && tabIds.includes(hash as TabId)) {
			activeTab = hash as TabId;
		}
	});

	function setTab(id: TabId) {
		activeTab = id;
		goto(`#${id}`, { replaceState: true, noScroll: true });
	}

	const companyQuery = createQuery(() => ({
		queryKey: ["company", slug],
		queryFn: () => getCompany(slug) as Promise<CompanyDetailResponse>,
		enabled: Boolean(slug),
	}));

	const profileClaimsQuery = createQuery(() => ({
		queryKey: ["company-profile-claims", slug],
		queryFn: () => getCompanyProfileClaims(slug),
		enabled: Boolean(slug) && activeTab === "overview",
	}));

	const jobsQuery = createQuery(() => ({
		queryKey: ["company-jobs", slug],
		queryFn: () => getJobsForCompany(slug) as Promise<CompanyJobsResponse>,
		enabled: Boolean(slug) && (activeTab === "jobs" || activeTab === "overview"),
	}));

	const detail = $derived(companyQuery.data);
	const jobsData = $derived(jobsQuery.data);
	const company = $derived(detail?.company);
	const summary = $derived(detail?.summary);
	const totalRaised = $derived(summary?.total_raised_usd ?? 0);
	const verifiedRaised = $derived(summary?.verified_raised_usd ?? 0);
	const fundingConfidence = $derived(summary?.max_funding_corroboration ?? null);
	const detailsProvenance = $derived.by(() => {
		const raw = detail?.details as { fields_provenance?: Record<string, unknown> | string } | null | undefined;
		if (!raw?.fields_provenance) return null;
		if (typeof raw.fields_provenance === "string") {
			try {
				return JSON.parse(raw.fields_provenance) as Record<string, unknown>;
			} catch {
				return null;
			}
		}
		return raw.fields_provenance;
	});
	const leadershipCount = $derived(summary?.team_size ?? 0);
	const productCount = $derived(summary?.products ?? 0);
	const licenseCount = $derived(summary?.licenses ?? 0);
	const valuation = $derived(detail?.valuation);
	const valuationIsEstimated = $derived(valuation?.valuation_kind === "estimated");
	const detailsRecord = $derived(
		(detail?.details as Record<string, unknown> | null | undefined) ?? null,
	);

	function claimValue(
		claims: CompanyProfileClaimsResponse | undefined,
		fieldKey: string,
	): string | null {
		const row = claims?.profile_claims?.find((c) => c.field_key === fieldKey);
		const val = row?.field_value?.trim();
		return val || null;
	}

	const profilePanelRows = $derived.by(() => {
		const claims = profileClaimsQuery.data;
		const rows: { label: string; value: string; hint?: string }[] = [];
		const legal = claimValue(claims, "legal_name");
		if (legal) rows.push({ label: "Legal name", value: legal, hint: "profile claim" });
		const yc = claimValue(claims, "yc_batch");
		if (yc) rows.push({ label: "YC batch", value: yc, hint: "profile claim" });
		const ycStatus = claimValue(claims, "yc_status");
		if (ycStatus) rows.push({ label: "YC status", value: ycStatus });
		const hq =
			(detailsRecord?.headquarters as string | undefined) ??
			claimValue(claims, "headquarters");
		if (hq) rows.push({ label: "Headquarters", value: String(hq) });
		const founded =
			detailsRecord?.founded_year != null
				? String(detailsRecord.founded_year)
				: claimValue(claims, "founded_year");
		if (founded) rows.push({ label: "Founded", value: founded });
		const model = detailsRecord?.business_model as string | undefined;
		if (model) rows.push({ label: "Business model", value: String(model) });
		const teamSize = detailsRecord?.team_size as number | undefined;
		if (teamSize != null && teamSize > 0) {
			const src = detailsRecord?.team_size_source as string | undefined;
			rows.push({
				label: "Team size (profile)",
				value: String(teamSize),
				hint: src ? `source: ${src}` : undefined,
			});
		}
		const longDesc = detailsRecord?.description_long as string | undefined;
		if (longDesc) {
			rows.push({ label: "Profile", value: truncate(String(longDesc), 280) });
		}
		return rows;
	});

	const hasProfilePanel = $derived(profilePanelRows.length > 0);

	const tabs = [
		{ id: "overview" as const, label: "Overview", icon: Activity },
		{ id: "signals" as const, label: "Signals", icon: Radio },
		{ id: "funding" as const, label: "Funding", icon: Wallet },
		{ id: "cap_table" as const, label: "Cap table", icon: Scale },
		{ id: "jobs" as const, label: "Jobs", icon: Briefcase },
		{ id: "team" as const, label: "Team", icon: Users },
		{ id: "products" as const, label: "Products", icon: Package },
		{ id: "licenses" as const, label: "Licenses", icon: Shield },
		{ id: "tech" as const, label: "Tech", icon: Box },
	];

	function statusTone(status: string) {
		const map: Record<string, string> = {
			active: "border-[var(--color-healthy)]/30 text-[var(--color-healthy)] bg-[rgba(52,211,153,0.1)]",
			acquired: "border-[var(--color-cyan)]/30 text-[var(--color-cyan)] bg-[var(--color-cyan-dim)]",
			dead: "border-[var(--color-stale)]/30 text-[var(--color-stale)] bg-[rgba(248,113,113,0.1)]",
		};
		return map[status] ?? map.active;
	}
</script>

<div class="ci-page">
	{#if companyQuery.isPending}
		<div class="ci-skeleton mb-6 h-40"></div>
		<div class="ci-bento">
			{#each [1, 2, 3, 4, 5, 6] as _}
				<div class="ci-span-4 ci-skeleton h-28"></div>
			{/each}
		</div>
	{:else if companyQuery.isError}
		<div class="ci-alert-error" role="alert">
			{companyQuery.error?.message ?? "Failed to load company"}
		</div>
	{:else if detail && company && summary}
		<a href="/companies" class="ci-btn mb-6">
			<ArrowLeft size={16} />
			Companies
		</a>

		<header class="ci-panel-glow relative mb-8 overflow-hidden p-6 sm:p-8">
			<div
				class="pointer-events-none absolute inset-0 bg-gradient-to-br from-[var(--color-cyan-dim)] via-transparent to-[var(--color-magenta-dim)] opacity-80"
				aria-hidden="true"
			></div>
			<div class="relative flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
				<div class="min-w-0">
					<div class="mb-3 flex flex-wrap items-center gap-2">
						<span class="ci-badge border {statusTone(company.status)}">{company.status}</span>
						<span class="ci-mono text-xs text-[var(--color-ink-faint)]">/{company.slug}</span>
					</div>
					<h1 class="ci-display text-4xl font-bold tracking-tight sm:text-5xl">{company.name}</h1>
					<p class="mt-2 text-base text-[var(--color-ink-muted)]">
						{company.industry ?? "AI / Technology"}
						{#if company.description}
							· {truncate(String(company.description), 120)}
						{/if}
					</p>
				</div>
				<div class="flex shrink-0 flex-wrap gap-2">
					{#if company.website}
						<a
							href={company.website}
							target="_blank"
							rel="noopener noreferrer"
							class="ci-btn"
						>
							<ExternalLink size={16} />
							Website
						</a>
					{/if}
					{#if company.github_org}
						<a
							href={`https://github.com/${company.github_org}`}
							target="_blank"
							rel="noopener noreferrer"
							class="ci-btn"
						>
							<GitBranch size={16} />
							GitHub
						</a>
					{/if}
					{#if company.x_handle}
						<a
							href={`https://x.com/${company.x_handle}`}
							target="_blank"
							rel="noopener noreferrer"
							class="ci-btn"
						>
							@{company.x_handle}
						</a>
					{/if}
				</div>
			</div>

			<div class="relative mt-8 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-5">
				<div class="ci-kpi border-0 bg-[var(--color-base)]/80">
					<p class="ci-kpi-label">Signals</p>
					<p class="ci-kpi-value">{summary.signals}</p>
				</div>
				<div class="ci-kpi border-0 bg-[var(--color-base)]/80">
					<p class="ci-kpi-label">Events</p>
					<p class="ci-kpi-value">{summary.events}</p>
				</div>
				<div class="ci-kpi border-0 bg-[var(--color-base)]/80">
					<p class="ci-kpi-label">Active jobs</p>
					<p class="ci-kpi-value">{summary.active_jobs}</p>
				</div>
				<div class="ci-kpi border-0 bg-[var(--color-base)]/80">
					<p class="ci-kpi-label">Rounds</p>
					<p class="ci-kpi-value">{summary.funding_rounds}</p>
				</div>
				<div class="ci-kpi border-0 bg-[var(--color-base)]/80">
					<p class="ci-kpi-label">Total raised</p>
					<p class="ci-kpi-value text-lg">
						{totalRaised > 0 ? formatUsd(totalRaised) : "—"}
					</p>
					{#if (summary.funding_rounds ?? 0) > 0}
						<p class="mt-1 text-[0.65rem] text-[var(--color-ink-faint)]">
							Confidence {confidencePercent(fundingConfidence)} (best round)
						</p>
					{/if}
				</div>
				<div class="ci-kpi border-0 bg-[var(--color-base)]/80">
					<p class="ci-kpi-label">Verified raised</p>
					<p class="ci-kpi-value text-lg">
						{verifiedRaised > 0 ? formatUsd(verifiedRaised) : "—"}
					</p>
					<p class="mt-1 text-[0.65rem] text-[var(--color-ink-faint)]">Rounds ≥45% corroboration</p>
				</div>
				<div class="ci-kpi border-0 bg-[var(--color-base)]/80">
					<p class="ci-kpi-label">
						{valuationIsEstimated ? "Est. valuation" : "Valuation"}
					</p>
					<p class="ci-kpi-value text-lg">
						{valuation?.valuation_usd ? formatUsd(valuation.valuation_usd) : "—"}
					</p>
					{#if valuation}
						<p class="mt-1 text-[0.65rem] text-[var(--color-ink-faint)]">
							{valuationIsEstimated ? "Estimated" : "Reported"}
							· {confidencePercent(valuation.confidence)}
						</p>
					{/if}
				</div>
				<div class="ci-kpi border-0 bg-[var(--color-base)]/80">
					<p class="ci-kpi-label">Leadership</p>
					<p class="ci-kpi-value">{leadershipCount > 0 ? leadershipCount : "—"}</p>
					{#if leadershipCount === 0}
						<p class="mt-1 text-[0.65rem] text-[var(--color-ink-faint)]">Not collected yet</p>
					{/if}
				</div>
				<div class="ci-kpi border-0 bg-[var(--color-base)]/80">
					<p class="ci-kpi-label">Products</p>
					<p class="ci-kpi-value">{productCount > 0 ? productCount : "—"}</p>
				</div>
				<div class="ci-kpi border-0 bg-[var(--color-base)]/80">
					<p class="ci-kpi-label">Licenses</p>
					<p class="ci-kpi-value">{licenseCount > 0 ? licenseCount : "—"}</p>
				</div>
			</div>
		</header>

		<nav class="mb-6 flex gap-1 overflow-x-auto border-b border-[var(--color-border)]" aria-label="Company sections">
			{#each tabs as tab}
				<button
					type="button"
					class="ci-tab whitespace-nowrap {activeTab === tab.id ? 'ci-tab-active' : ''}"
					onclick={() => setTab(tab.id)}
				>
					<tab.icon size={16} aria-hidden="true" />
					{tab.label}
				</button>
			{/each}
		</nav>

		{#if activeTab === "overview"}
			<div class="ci-bento">
				{#if profileClaimsQuery.isPending && !hasProfilePanel}
					<section class="ci-span-12 ci-panel p-5">
						<div class="ci-skeleton h-24"></div>
					</section>
				{:else if hasProfilePanel}
					<section class="ci-span-12 ci-panel p-5">
						<h2 class="text-sm font-semibold text-[var(--color-ink)]">Company profile</h2>
						<p class="mt-1 text-xs text-[var(--color-ink-faint)]">
							From enriched <code class="ci-mono">company_details</code> and corroborated profile claims.
						</p>
						<dl class="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
							{#each profilePanelRows as row}
								<div class="rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] p-3">
									<dt class="text-xs font-medium uppercase tracking-wide text-[var(--color-ink-faint)]">
										{row.label}
									</dt>
									<dd class="mt-1 text-sm text-[var(--color-ink)]">{row.value}</dd>
									{#if row.hint}
										<p class="mt-1 text-[0.65rem] text-[var(--color-ink-faint)]">{row.hint}</p>
									{/if}
								</div>
							{/each}
						</dl>
					</section>
				{/if}

				<section class="ci-span-8 ci-panel p-5">
					<h2 class="text-sm font-semibold text-[var(--color-ink)]">Recent intelligence</h2>
					<ul class="mt-4 space-y-3" role="list">
						{#each detail.recent_events.slice(0, 6) as ev}
							{@const evLabel = eventConfidenceLabel(ev.confidence as number | null | undefined)}
							<li class="flex items-start justify-between gap-3 border-b border-[var(--color-border)]/50 pb-3 last:border-0">
								<div class="min-w-0">
									<div class="mb-1 flex flex-wrap items-center gap-2">
										<p class="text-sm font-medium">{formatEventType(String(ev.event_type))}</p>
										<SourceTag label={evLabel} />
									</div>
									{#if ev.amount_usd}
										<p class="ci-mono text-xs text-[var(--color-magenta)]">{formatUsd(Number(ev.amount_usd))}</p>
									{/if}
								</div>
								<time class="ci-mono text-xs text-[var(--color-ink-faint)]">{String(ev.created_at ?? "").slice(0, 10)}</time>
							</li>
						{:else}
							<li class="text-sm text-[var(--color-ink-faint)]">No events yet</li>
						{/each}
					</ul>
				</section>

				<section class="ci-span-4 ci-panel p-5">
					<h2 class="text-sm font-semibold">GitHub</h2>
					{#if detail.github}
						<dl class="mt-4 space-y-2 text-sm">
							<div class="flex justify-between">
								<dt class="text-[var(--color-ink-faint)]">Stars</dt>
								<dd class="ci-mono">{Number(company.github_stars ?? detail.github.stars ?? 0).toLocaleString()}</dd>
							</div>
							<div class="flex justify-between">
								<dt class="text-[var(--color-ink-faint)]">Commits</dt>
								<dd class="ci-mono">{Number(detail.github.total_commits ?? 0).toLocaleString()}</dd>
							</div>
						</dl>
					{:else}
						<p class="mt-4 text-sm text-[var(--color-ink-faint)]">No GitHub metrics</p>
					{/if}
				</section>

				{#if detail.competitors.length}
					<section class="ci-span-12 ci-panel p-5">
						<h2 class="text-sm font-semibold">Competitive set</h2>
						<div class="mt-3 flex flex-wrap gap-2">
							{#each detail.competitors as rel}
								<a
									href="/companies/{rel.slug ?? rel.name}"
									class="ci-badge border border-[var(--color-border)] bg-[var(--color-surface-2)] text-[var(--color-ink-muted)] hover:border-[var(--color-cyan)]"
								>
									{rel.name}
								</a>
							{/each}
						</div>
					</section>
				{/if}

				{#if jobsData?.jobs?.length}
					<section class="ci-span-12 ci-panel p-5">
						<h2 class="text-sm font-semibold">Hiring pulse</h2>
						<ul class="mt-3 grid gap-2 sm:grid-cols-2" role="list">
							{#each jobsData.jobs.slice(0, 4) as job}
								<li>
									<a href="/jobs/{job.id}" class="block rounded-lg border border-[var(--color-border)] p-3 hover:border-[var(--color-cyan)]">
										<p class="font-medium text-sm">{job.title}</p>
										<p class="text-xs text-[var(--color-ink-faint)] mt-1">{job.location ?? "Remote"}</p>
									</a>
								</li>
							{/each}
						</ul>
					</section>
				{/if}
			</div>
		{:else if activeTab === "signals"}
			<section class="ci-panel p-5">
				<h2 class="text-sm font-semibold mb-4">Signal feed</h2>
				<ul class="space-y-3" role="list">
					{#each detail.recent_signals as sig}
						<li class="rounded-xl border border-[var(--color-border)] bg-[var(--color-base)] p-4">
							<div class="flex items-center justify-between gap-2 mb-2">
								<div class="flex flex-wrap items-center gap-2">
									<span class="ci-badge border border-[var(--color-cyan)]/30 text-[var(--color-cyan)] bg-[var(--color-cyan-dim)]">
										{sig.source}
									</span>
									<SourceTag
										label={confidenceLabel(
											(sig.confidence as number | null | undefined) ?? 0.2,
										)}
									/>
								</div>
								<time class="ci-mono text-xs text-[var(--color-ink-faint)]">{String(sig.detected_at ?? "").slice(0, 16)}</time>
							</div>
							<p class="text-sm leading-relaxed">{parseSignalPreview(String(sig.data_json ?? ""))}</p>
						</li>
					{:else}
						<li class="text-sm text-[var(--color-ink-faint)]">No signals linked to this company</li>
					{/each}
				</ul>
			</section>
		{:else if activeTab === "funding"}
			{#if detailsProvenance && Object.keys(detailsProvenance).length}
				<p class="mb-4 text-xs text-[var(--color-ink-faint)]">
					Field provenance on company profile:
					{Object.keys(detailsProvenance).slice(0, 8).join(", ")}
					{#if Object.keys(detailsProvenance).length > 8}…{/if}
				</p>
			{/if}
			{#if detail.funding.length}
				<div class="ci-panel ci-table-wrap">
					<table class="ci-table min-w-[900px]">
						<thead>
							<tr>
								<th>Round</th>
								<th>Amount</th>
								<th>Date</th>
								<th>Lead</th>
								<th>Sources</th>
								<th>Investors</th>
								<th>Confidence</th>
							</tr>
						</thead>
						<tbody>
							{#each detail.funding as round}
								{@const sources = (round.sources as unknown[] | undefined) ?? []}
								{@const participants = (round.participants as unknown[] | undefined) ?? []}
								<tr>
									<td>
										<a href="/funding/{round.id}" class="ci-link font-medium">{round.round_type ?? "Round"}</a>
									</td>
									<td class="ci-mono">{formatUsd(round.amount_usd as number | null)}</td>
									<td class="text-[var(--color-ink-muted)]">{round.announced_date ?? "—"}</td>
									<td>{round.lead_investor ?? "—"}</td>
									<td class="tabular-nums text-[var(--color-ink-muted)]">{sources.length}</td>
									<td class="tabular-nums text-[var(--color-ink-muted)]">{participants.length}</td>
									<td>
										<CorroborationBadge
											labeled
											score={round.corroboration_score as number | null}
											officialCount={round.official_report_count as number | null}
											reportCount={round.report_count as number | null}
										/>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{:else}
				<p class="text-[var(--color-ink-faint)]">No funding rounds</p>
			{/if}
		{:else if activeTab === "cap_table"}
			<p class="mb-4 text-sm text-[var(--color-ink-muted)]">
				Investors from corroborated funding rounds. Ownership percentages appear when filings supply them.
			</p>
			{#if detail.cap_table?.length}
				<div class="ci-panel ci-table-wrap">
					<table class="ci-table min-w-[720px]">
						<thead>
							<tr>
								<th>Holder</th>
								<th>Class</th>
								<th>As of</th>
								<th>Ownership</th>
								<th>Confidence</th>
							</tr>
						</thead>
						<tbody>
							{#each detail.cap_table as row}
								<tr>
									<td class="font-medium">{String(row.holder_name ?? "—")}</td>
									<td>{String(row.share_class ?? "—")}</td>
									<td class="text-[var(--color-ink-muted)]">{String(row.as_of_date ?? "—").slice(0, 10)}</td>
									<td class="ci-mono">
										{row.ownership_pct != null ? `${Number(row.ownership_pct).toFixed(2)}%` : "—"}
									</td>
									<td>
										<CorroborationBadge
											score={row.confidence as number | null}
											labeled={false}
										/>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{:else}
				<p class="text-[var(--color-ink-faint)]">No cap table rows — run funding rollup then cap table rollup</p>
			{/if}
		{:else if activeTab === "jobs"}
			<p class="mb-4 text-sm text-[var(--color-ink-muted)]">
				Roles from career sites and ATS boards — hiring signal, not leadership or filing-backed org data.
			</p>
			{#if jobsQuery.isPending}
				<div class="ci-skeleton h-48"></div>
			{:else if jobsData?.jobs?.length}
				<p class="text-sm text-[var(--color-ink-muted)] mb-4">
					{jobsData.stats?.total_active ?? jobsData.jobs.length} active roles
				</p>
				<ul class="grid gap-3 sm:grid-cols-2" role="list">
					{#each jobsData.jobs as job}
						<li>
							<a href="/jobs/{job.id}" class="ci-panel block p-4 hover:border-[var(--color-cyan)]">
								<p class="font-medium">{job.title}</p>
								<p class="text-sm text-[var(--color-ink-muted)] mt-1">
									{formatSeniority(job.seniority_band as string | null)}
									{#if job.location}· {job.location}{/if}
								</p>
							</a>
						</li>
					{/each}
				</ul>
			{:else}
				<p class="text-[var(--color-ink-faint)]">No active job postings</p>
			{/if}
		{:else if activeTab === "team"}
			<p class="mb-4 text-sm text-[var(--color-ink-muted)]">
				Canonical leadership rows from filings and corroborated claims. Job postings are hiring signals, not org charts.
			</p>
			{#if detail.team.length}
				<ul class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" role="list">
					{#each detail.team as member}
						<li class="ci-panel p-4">
							<p class="font-medium">{member.name}</p>
							<p class="text-sm text-[var(--color-ink-muted)]">{member.role ?? "—"}</p>
							{#if member.joined_date}
								<p class="ci-mono text-xs text-[var(--color-ink-faint)] mt-2">Joined {member.joined_date}</p>
							{/if}
							<div class="mt-2">
								<CorroborationBadge
									score={member.corroboration_score as number | null}
									reportCount={member.report_count as number | null}
									size="sm"
								/>
							</div>
						</li>
					{/each}
				</ul>
			{:else}
				<p class="text-[var(--color-ink-faint)]">
					No canonical team rows — run company enrich or wait for SEC / YC profile extraction.
				</p>
			{/if}
		{:else if activeTab === "products"}
			{#if detail.products.length}
				<ul class="grid gap-3 sm:grid-cols-2" role="list">
					{#each detail.products as product}
						<li class="ci-panel p-4">
							<p class="font-medium">{String(product.name ?? product.product_name ?? "Product")}</p>
							{#if product.status}
								<p class="text-xs text-[var(--color-ink-faint)] mt-1">{String(product.status)}</p>
							{/if}
							{#if product.launch_date}
								<p class="ci-mono text-xs text-[var(--color-ink-faint)] mt-1">Launch {String(product.launch_date)}</p>
							{/if}
							<div class="mt-2">
								<CorroborationBadge
									score={product.corroboration_score as number | null}
									reportCount={product.report_count as number | null}
									size="sm"
								/>
							</div>
						</li>
					{/each}
				</ul>
			{:else}
				<p class="text-[var(--color-ink-faint)]">No product records — run company enrich or wait for signal extraction.</p>
			{/if}
		{:else if activeTab === "licenses"}
			<p class="mb-4 text-sm text-[var(--color-ink-muted)]">
				Regulatory filings and license claims from SEC, ESMA, and regulatory RSS.
			</p>
			{#if detail.licenses?.length}
				<h3 class="mb-2 text-sm font-semibold">Regulatory licenses</h3>
				<ul class="mb-6 grid gap-3 sm:grid-cols-2" role="list">
					{#each detail.licenses as lic}
						<li class="ci-panel p-4">
							<p class="font-medium">{String(lic.license_type ?? "License")}</p>
							<p class="text-sm text-[var(--color-ink-muted)]">
								{String(lic.jurisdiction ?? "—")}
								{#if lic.regulator}· {String(lic.regulator)}{/if}
							</p>
							{#if lic.effective_date}
								<p class="ci-mono text-xs text-[var(--color-ink-faint)] mt-2">
									Effective {String(lic.effective_date).slice(0, 10)}
								</p>
							{/if}
							<div class="mt-2">
								<CorroborationBadge score={lic.corroboration_score as number | null} />
							</div>
						</li>
					{/each}
				</ul>
			{/if}
			{#if detail.license_claims?.length}
				<h3 class="mb-2 text-sm font-semibold">License claims</h3>
				<ul class="grid gap-3 sm:grid-cols-2" role="list">
					{#each detail.license_claims as claim}
						<li class="ci-panel p-4">
							<p class="font-medium">{String(claim.license_type ?? "Claim")}</p>
							<p class="text-sm text-[var(--color-ink-muted)]">
								{String(claim.jurisdiction ?? "—")}
								{#if claim.regulator}· {String(claim.regulator)}{/if}
								· {String(claim.status ?? "—")}
							</p>
							{#if claim.snippet}
								<p class="mt-2 text-xs leading-relaxed text-[var(--color-ink-faint)]">
									{truncate(String(claim.snippet), 160)}
								</p>
							{/if}
							<div class="mt-2 flex flex-wrap items-center gap-2">
								<SourceTag
									label={confidenceLabel(
										(claim.extraction_confidence as number | null | undefined) ?? 0.5,
									)}
								/>
								<CorroborationBadge score={claim.extraction_confidence as number | null} />
							</div>
						</li>
					{/each}
				</ul>
			{:else if !detail.licenses?.length}
				<p class="text-[var(--color-ink-faint)]">No license data</p>
			{/if}
		{:else if activeTab === "tech"}
			{#if detail.tech_stack.length}
				<div class="flex flex-wrap gap-2">
					{#each detail.tech_stack as tech}
						<span
							class="ci-badge border border-[var(--color-magenta)]/25 bg-[var(--color-magenta-dim)] text-[var(--color-magenta)]"
						>
							{tech.technology}
							<span class="ci-mono ml-1 opacity-70">{Math.round(tech.confidence * 100)}%</span>
						</span>
					{/each}
				</div>
			{:else}
				<p class="text-[var(--color-ink-faint)]">No tech stack data</p>
			{/if}
		{/if}
	{:else}
		<p class="text-[var(--color-ink-faint)]">Company not found</p>
	{/if}
</div>
