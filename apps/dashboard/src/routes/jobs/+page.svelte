<script lang="ts">
	import { createQuery } from "@tanstack/svelte-query";
	import { getJobClaims, getJobs } from "$lib/api";
	import { formatSeniority, formatUsd } from "$lib/format";
	import type { JobClaimRow, JobPostingRow, JobsListResponse } from "$lib/types/structured-intel";
	import CorroborationBadge from "$lib/components/CorroborationBadge.svelte";
	import EmptyState from "$lib/components/EmptyState.svelte";
	import SearchBar from "$lib/components/SearchBar.svelte";
	import PageHeader from "$lib/components/PageHeader.svelte";
	import { Briefcase, FileText } from "lucide-svelte";

	type View = "postings" | "claims";

	let view = $state<View>("postings");

	const jobsQuery = createQuery(() => ({
		queryKey: ["jobs", "active"],
		queryFn: () => getJobs({ limit: 200, active: true }) as Promise<JobsListResponse>,
	}));

	const claimsQuery = createQuery(() => ({
		queryKey: ["jobs", "claims"],
		queryFn: async () => {
			const res = await getJobClaims({ limit: 120 });
			return res.claims as JobClaimRow[];
		},
	}));

	const list = $derived(jobsQuery.data ?? null);
	const claims = $derived(claimsQuery.data ?? []);
	const loading = $derived(jobsQuery.isPending || claimsQuery.isPending);
	const error = $derived(jobsQuery.error?.message ?? claimsQuery.error?.message ?? null);

	function salaryRange(row: JobPostingRow): string {
		if (row.salary_min_usd == null && row.salary_max_usd == null) return "—";
		if (row.salary_min_usd != null && row.salary_max_usd != null) {
			return `${formatUsd(row.salary_min_usd)} – ${formatUsd(row.salary_max_usd)}`;
		}
		return formatUsd(row.salary_min_usd ?? row.salary_max_usd);
	}
</script>

<div class="ci-page">
	<PageHeader
		title="Jobs"
		subtitle="Hiring rollup: ATS and board claims merge into canonical postings with skills and corroboration."
	>
		{#snippet actions()}
			<SearchBar />
		{/snippet}
	</PageHeader>

	{#if error}
		<div class="ci-alert-error mb-6" role="alert">{error}</div>
	{/if}

	{#if list && !loading}
		{@const stats = list.stats ?? {
			active_postings: list.count ?? list.jobs?.length ?? 0,
			total_claims: 0,
			total_skills: 0,
			verified_boards: 0,
		}}
		<div class="mb-8 grid grid-cols-2 gap-4 lg:grid-cols-4">
			{#each [
				{ label: "Active postings", value: stats.active_postings },
				{ label: "Source claims", value: stats.total_claims },
				{ label: "Skills tracked", value: stats.total_skills },
				{ label: "Verified boards", value: stats.verified_boards },
			] as stat}
				<div class="ci-panel p-4">
					<p class="text-xs font-semibold uppercase tracking-wider text-[var(--color-ink-faint)]">{stat.label}</p>
					<p class="ci-display mt-1 text-xl font-medium tabular-nums text-[var(--color-ink)]">{stat.value}</p>
				</div>
			{/each}
		</div>
	{/if}

	<nav class="mb-6 flex gap-1 border-b border-[var(--color-border-subtle)]" aria-label="Jobs views">
		<button
			type="button"
			onclick={() => (view = "postings")}
			class="ci-tab {view === 'postings' ? 'ci-tab-active' : ''}"
		>
			<Briefcase size={16} aria-hidden="true" />
			Canonical postings
		</button>
		<button
			type="button"
			onclick={() => (view = "claims")}
			class="ci-tab {view === 'claims' ? 'ci-tab-active' : ''}"
		>
			<FileText size={16} aria-hidden="true" />
			Source claims
		</button>
	</nav>

	{#if loading}
		<div class="ci-skeleton h-64"></div>
	{:else if view === "postings" && list}
		{#if list.jobs.length === 0}
			<EmptyState
				title="No job postings yet"
				description="Run make job-rollup after collectors ingest career pages and ATS feeds."
			/>
		{:else}
			<div class="ci-panel ci-table-wrap">
				<table class="ci-table min-w-[800px]">
					<thead>
						<tr>
							<th>Role</th>
							<th>Company</th>
							<th>Level</th>
							<th>Location</th>
							<th>Salary</th>
							<th>Corroboration</th>
							<th>Skills</th>
						</tr>
					</thead>
					<tbody>
						{#each list.jobs as job (job.id)}
							<tr>
								<td class="font-medium">
									<a href="/jobs/{job.id}" class="ci-link">{job.title}</a>
								</td>
								<td>{job.company_name}</td>
								<td class="text-[var(--color-ink-muted)]">{formatSeniority(job.seniority_band)}</td>
								<td class="text-[var(--color-ink-muted)]">{job.location ?? job.remote_policy ?? "—"}</td>
								<td class="tabular-nums text-[var(--color-ink-muted)]">{salaryRange(job)}</td>
								<td>
									<CorroborationBadge
										score={job.corroboration_score}
										reportCount={job.report_count}
									/>
								</td>
								<td class="tabular-nums text-[var(--color-ink-muted)]">{job.skill_count ?? 0}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{:else if view === "claims"}
		{#if claims.length === 0}
			<EmptyState title="No job claims" description="Claims are extracted from career pages and job boards." />
		{:else}
			<ul class="space-y-3" role="list">
				{#each claims as claim (claim.id)}
					<li class="ci-panel p-4">
						<div class="flex flex-wrap justify-between gap-3">
							<div class="min-w-0">
								<p class="font-medium text-[var(--color-ink)]">
									{claim.title ?? "Untitled role"}
								</p>
								<p class="text-sm text-[var(--color-ink-muted)]">{claim.company_name}</p>
								{#if claim.skills?.length}
									<p class="mt-2 text-xs text-[var(--color-ink-faint)]">
										{claim.skills
											.slice(0, 6)
											.map((s) => s.skill)
											.join(" · ")}
									</p>
								{/if}
							</div>
							<a
								href={claim.source_url}
								target="_blank"
								rel="noopener noreferrer"
								class="ci-link shrink-0 text-xs"
							>
								Source
							</a>
						</div>
					</li>
				{/each}
			</ul>
		{/if}
	{/if}
</div>
