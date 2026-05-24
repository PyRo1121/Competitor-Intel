<script lang="ts">
	import { onMount } from "svelte";
	import { getDataAudit } from "$lib/api";
	import type { DataAuditDomain, DataAuditResponse, TrustTier } from "$lib/types/dataAudit";
	import { Shield, AlertTriangle, Database, Layout } from "lucide-svelte";

	let audit = $state<DataAuditResponse | null>(null);
	let error = $state<string | null>(null);
	let loading = $state(true);
	let tierFilter = $state<TrustTier | "all">("all");

	onMount(async () => {
		try {
			audit = await getDataAudit();
		} catch (e) {
			error = e instanceof Error ? e.message : "Failed to load audit";
		} finally {
			loading = false;
		}
	});

	const filteredDomains = $derived(
		audit
			? tierFilter === "all"
				? audit.domains
				: audit.domains.filter((d) => d.tier === tierFilter)
			: [],
	);

	function tierClass(tier: TrustTier): string {
		const map: Record<TrustTier, string> = {
			verified:
				"border-[var(--color-healthy)]/30 text-[var(--color-healthy)] bg-[rgba(52,211,153,0.08)]",
			corroborated:
				"border-[var(--color-cyan)]/30 text-[var(--color-cyan)] bg-[var(--color-cyan-dim)]",
			operational:
				"border-[var(--color-border)] text-[var(--color-ink-muted)] bg-[var(--color-surface-2)]",
			partial:
				"border-[var(--color-warning)]/30 text-[var(--color-warning)] bg-[rgba(251,191,36,0.08)]",
			empty: "border-[var(--color-stale)]/30 text-[var(--color-stale)] bg-[rgba(248,113,113,0.08)]",
			inferred:
				"border-[var(--color-magenta)]/25 text-[var(--color-magenta)] bg-[var(--color-magenta-dim)]",
		};
		return map[tier];
	}
</script>

<div class="ci-page">
	<header class="mb-8">
		<div class="mb-2 flex items-center gap-2 text-[var(--color-cyan)]">
			<Shield size={22} aria-hidden="true" />
			<span class="text-xs font-semibold uppercase tracking-widest">Trust & provenance</span>
		</div>
		<h1 class="ci-display text-3xl font-bold tracking-tight sm:text-4xl">Data quality audit</h1>
		<p class="mt-2 max-w-3xl text-sm leading-relaxed text-[var(--color-ink-muted)]">
			Live map of every domain the dashboard can show: which table backs it, whether a collector
			runs, company coverage, and how much to trust it. Refresh after pipeline runs — counts come
			from the database at request time.
		</p>
	</header>

	{#if loading}
		<div class="ci-skeleton h-64"></div>
	{:else if error}
		<div class="ci-alert-error" role="alert">{error}</div>
	{:else if audit}
		{#if audit.highlights.leadershipEmpty || (audit.highlights.fundingLowCorroboration?.fundingUnverified ?? 0) > 0}
			<section
				class="ci-panel mb-6 border border-[var(--color-warning)]/30 bg-[rgba(251,191,36,0.06)] p-5"
				aria-labelledby="audit-warnings"
			>
				<h2 id="audit-warnings" class="flex items-center gap-2 text-sm font-semibold">
					<AlertTriangle size={18} class="text-[var(--color-warning)]" />
					Critical gaps
				</h2>
				<ul class="mt-3 space-y-2 text-sm text-[var(--color-ink-muted)]" role="list">
					{#if audit.highlights.leadershipEmpty}
						<li>
							<strong class="text-[var(--color-ink)]">Leadership / officers:</strong> zero rows —
							no SEC or state-registry ingest.
						</li>
					{/if}
					{#if audit.highlights.fundingLowCorroboration}
						<li>
							<strong class="text-[var(--color-ink)]">Funding:</strong>
							{audit.highlights.fundingLowCorroboration.fundingVerified ?? 0} rounds with stronger confidence ·
							{audit.highlights.fundingLowCorroboration.fundingUnverified ?? 0} still early signal
							rounds (of {audit.highlights.fundingLowCorroboration.rowCount} total).
						</li>
					{/if}
					<li>
						<strong class="text-[var(--color-ink)]">Enrichment:</strong>
						{audit.highlights.enrichmentCoveragePct}% of companies have
						<code class="ci-mono text-xs">company_details</code>.
					</li>
					<li>
						<strong class="text-[var(--color-ink)]">GitHub metrics:</strong>
						{audit.highlights.githubCoveragePct}% company coverage.
					</li>
				</ul>
			</section>
		{/if}

		<section class="mb-8">
			<h2 class="mb-3 text-sm font-semibold">Trust tiers</h2>
			<div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
				{#each audit.byTier as row}
					<button
						type="button"
						class="ci-panel p-4 text-left transition-colors hover:border-[var(--color-cyan)] {tierFilter === row.tier
							? 'border-[var(--color-cyan)]'
							: ''}"
						onclick={() => (tierFilter = tierFilter === row.tier ? 'all' : row.tier)}
					>
						<span class="ci-badge border {tierClass(row.tier)}">{row.label}</span>
						<p class="mt-2 text-xs leading-relaxed text-[var(--color-ink-muted)]">{row.description}</p>
						<p class="ci-mono mt-2 text-xs text-[var(--color-ink-faint)]">{row.domainCount} domains</p>
					</button>
				{/each}
			</div>
		</section>

		<section class="mb-8">
			<div class="mb-3 flex flex-wrap items-center justify-between gap-2">
				<h2 class="flex items-center gap-2 text-sm font-semibold">
					<Database size={18} />
					Data domains ({filteredDomains.length})
				</h2>
				{#if tierFilter !== "all"}
					<button type="button" class="ci-btn text-xs" onclick={() => (tierFilter = "all")}>
						Clear filter
					</button>
				{/if}
			</div>
			<div class="ci-panel ci-table-wrap">
				<table class="ci-table min-w-[960px]">
					<thead>
						<tr>
							<th>Domain</th>
							<th>Tier</th>
							<th>Rows</th>
							<th>Companies</th>
							<th>Pipeline</th>
							<th>Collector</th>
							<th>Guidance</th>
						</tr>
					</thead>
					<tbody>
						{#each filteredDomains as domain (domain.id)}
							<tr>
								<td>
									<p class="font-medium">{domain.name}</p>
									<p class="ci-mono text-xs text-[var(--color-ink-faint)]">{domain.table}</p>
								</td>
								<td>
									<span class="ci-badge border {tierClass(domain.tier)}">
										{audit.trustTiers[domain.tier].label}
									</span>
								</td>
								<td class="ci-mono">{domain.rowCount.toLocaleString()}</td>
								<td class="ci-mono">
									{domain.companiesWithData}/{domain.totalCompanies}
									<span class="text-[var(--color-ink-faint)]"> ({domain.coveragePct}%)</span>
								</td>
								<td class="text-xs capitalize">{domain.pipelineStatus.replace("_", " ")}</td>
								<td class="max-w-[12rem] text-xs text-[var(--color-ink-muted)]">
									{domain.collector ?? "—"}
								</td>
								<td class="max-w-md text-xs text-[var(--color-ink-muted)] leading-relaxed">
									{domain.guidance}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</section>

		<section class="mb-8">
			<h2 class="mb-3 flex items-center gap-2 text-sm font-semibold">
				<Layout size={18} />
				Dashboard surfaces
			</h2>
			<div class="grid gap-3 lg:grid-cols-2">
				{#each audit.dashboardSurfaces as surf}
					<article class="ci-panel p-4">
						<p class="font-medium">{surf.surface}</p>
						<p class="ci-mono text-xs text-[var(--color-cyan)]">{surf.path}</p>
						<p class="mt-2 text-xs text-[var(--color-ink-muted)]">{surf.notes}</p>
						<p class="mt-2 text-[0.65rem] text-[var(--color-ink-faint)]">
							Domains: {surf.domains.join(", ")}
						</p>
					</article>
				{/each}
			</div>
		</section>

		<section class="ci-panel p-5">
			<h2 class="text-sm font-semibold">Remediation order</h2>
			<ol class="mt-3 list-decimal space-y-2 pl-5 text-sm text-[var(--color-ink-muted)]">
				{#each audit.recommendations as item}
					<li>{item}</li>
				{/each}
			</ol>
			<p class="mt-4 text-xs text-[var(--color-ink-faint)]">
				Full reference: <code class="ci-mono">docs/DATA_AUDIT.md</code> · API:
				<code class="ci-mono">GET /api/data-audit</code> · audited {audit.auditedAt.slice(0, 19)}Z
			</p>
		</section>
	{/if}
</div>
