<script lang="ts">
	import { onMount } from "svelte";
	import { getFunding, getJobs, getStatus, getTopScored } from "$lib/api";
	import { formatEventType } from "$lib/freshness";
	import StatCard from "$lib/components/StatCard.svelte";
	import IntelHealthCard from "$lib/components/IntelHealthCard.svelte";
	import PageHeader from "$lib/components/PageHeader.svelte";
	import type { StatusResponse } from "$lib/types/status";
	import { ArrowRight, Clock } from "lucide-svelte";

	let status = $state<StatusResponse | null>(null);
	let loadError = $state<string | null>(null);
	let rollupSummary = $state<{ rounds: number; claims: number; activeJobs: number } | null>(null);
	let topAttention = $state<{ name: string; score: number; slug?: string | null }[]>([]);

	onMount(async () => {
		try {
			const [statusRes, fundingRes, jobsRes, scoredRes] = await Promise.all([
				getStatus(),
				getFunding().catch(() => null),
				getJobs({ limit: 1, active: true }).catch(() => null),
				getTopScored(5).catch(() => null),
			]);
			status = statusRes;
			if (fundingRes?.stats) {
				rollupSummary = {
					rounds: fundingRes.stats.total_rounds ?? 0,
					claims: fundingRes.stats.total_claims ?? 0,
					activeJobs: jobsRes?.stats?.active_postings ?? jobsRes?.count ?? 0,
				};
			}
			if (scoredRes?.companies?.length) {
				topAttention = scoredRes.companies
					.filter((c) => c.score != null)
					.map((c) => ({
						name: c.name,
						score: Number(c.score),
						slug: c.slug,
					}));
			}
		} catch (err) {
			loadError = err instanceof Error ? err.message : "Failed to load dashboard";
			console.error(err);
		}
	});

	function formatTime(iso: string) {
		const date = new Date(iso);
		if (Number.isNaN(date.getTime())) return "—";
		return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
	}
</script>

<div class="ci-page">
	<PageHeader
		title="Dashboard"
		subtitle="Operational picture of competitors — corpus size, ingest freshness, and what moved in the last day."
	/>

	{#if loadError}
		<div class="ci-alert-error mb-6" role="alert">
			{loadError}. Ensure the API is running at
			<code class="ci-mono text-[0.7rem] text-[var(--color-accent-bright)]">PUBLIC_CI_API_URL</code>.
		</div>
	{/if}

	{#if !status}
		<div class="space-y-6">
			<div class="ci-skeleton h-44"></div>
			<div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
				{#each [1, 2, 3, 4] as _}
					<div class="ci-skeleton h-28"></div>
				{/each}
			</div>
		</div>
	{:else}
		<div class="mb-8">
			<IntelHealthCard {status} apiReachable={!loadError} />
		</div>

		{#if rollupSummary}
			<div class="mb-8 grid gap-3 sm:grid-cols-2" aria-label="Structured intelligence corpus">
				<a href="/funding" class="ci-panel group flex items-center justify-between p-4 transition-colors hover:border-[var(--color-accent)]/40">
					<div>
						<p class="text-xs font-semibold uppercase tracking-wider text-[var(--color-ink-faint)]">Funding</p>
						<p class="ci-display mt-1 text-2xl font-medium tabular-nums text-[var(--color-ink)]">
							{rollupSummary.rounds}
							<span class="text-base font-normal text-[var(--color-ink-muted)]">rounds</span>
						</p>
						<p class="mt-0.5 text-xs text-[var(--color-ink-faint)]">{rollupSummary.claims} source claims</p>
					</div>
					<ArrowRight size={18} class="text-[var(--color-ink-faint)] group-hover:text-[var(--color-accent)]" />
				</a>
				<a href="/jobs" class="ci-panel group flex items-center justify-between p-4 transition-colors hover:border-[var(--color-accent)]/40">
					<div>
						<p class="text-xs font-semibold uppercase tracking-wider text-[var(--color-ink-faint)]">Jobs</p>
						<p class="ci-display mt-1 text-2xl font-medium tabular-nums text-[var(--color-ink)]">
							{rollupSummary.activeJobs}
							<span class="text-base font-normal text-[var(--color-ink-muted)]">active</span>
						</p>
						<p class="mt-0.5 text-xs text-[var(--color-ink-faint)]">Canonical postings</p>
					</div>
					<ArrowRight size={18} class="text-[var(--color-ink-faint)] group-hover:text-[var(--color-accent)]" />
				</a>
			</div>
		{/if}

		{#if topAttention.length > 0}
			<section class="ci-panel group mb-8 p-4">
				<div class="mb-3 flex items-center justify-between">
					<a
						href="/discovery"
						class="text-xs font-semibold uppercase tracking-wider text-[var(--color-ink-faint)] hover:text-[var(--color-accent)]"
					>
						Top attention (30d)
					</a>
					<a
						href="/discovery"
						class="text-[var(--color-ink-faint)] hover:text-[var(--color-accent)]"
						aria-label="View discovery"
					>
						<ArrowRight size={18} />
					</a>
				</div>
				<ol class="grid gap-2 sm:grid-cols-5">
					{#each topAttention as row, i}
						<li class="text-sm">
							<span class="ci-mono text-xs text-[var(--color-ink-faint)]">{i + 1}.</span>
							{#if row.slug}
								<a href={`/companies/${row.slug}`} class="ci-link ml-1 font-medium">{row.name}</a>
							{:else}
								<span class="ml-1 font-medium">{row.name}</span>
							{/if}
							<span class="ci-mono ml-2 text-xs text-[var(--color-accent-bright)]">
								{row.score.toFixed(2)}
							</span>
						</li>
					{/each}
				</ol>
			</section>
		{/if}

		<div class="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
			<StatCard title="Companies" value={status.counts.companies} icon="chart" />
			<StatCard
				title="Signals"
				value={status.counts.signals}
				change={`${status.last24h.signals} in 24h`}
				icon="activity"
			/>
			<StatCard
				title="Events"
				value={status.counts.events}
				change={`${status.last24h.events} in 24h`}
				icon="zap"
			/>
			<StatCard title="Funding rounds" value={status.counts.funding} icon="dollar" />
		</div>

		<div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
			<section class="ci-panel" aria-labelledby="top-sources-heading">
				<div class="ci-panel-header">
					<h2 id="top-sources-heading" class="text-sm font-semibold text-[var(--color-ink)]">Top sources</h2>
				</div>
				<ul class="divide-y divide-[var(--color-border-subtle)]" role="list">
					{#each status.topSources as src (src.source)}
						<li class="flex items-center justify-between px-5 py-3.5 sm:px-6">
							<span class="text-sm text-[var(--color-ink-muted)]">{src.source}</span>
							<span class="ci-mono text-sm font-medium text-[var(--color-ink)]">
								{src.count.toLocaleString()}
							</span>
						</li>
					{/each}
				</ul>
			</section>

			<section class="ci-panel" aria-labelledby="recent-events-heading">
				<div class="ci-panel-header">
					<h2 id="recent-events-heading" class="text-sm font-semibold text-[var(--color-ink)]">Recent events</h2>
				</div>
				<ul class="divide-y divide-[var(--color-border-subtle)]" role="list">
					{#each status.recentEvents as ev (ev.created_at + ev.event_type)}
						<li class="flex items-center justify-between gap-3 px-5 py-3.5 sm:px-6">
							<div class="min-w-0">
								<span class="text-sm font-medium text-[var(--color-ink)]">
									{formatEventType(ev.event_type)}
								</span>
								{#if ev.company_name}
									<span class="ml-2 text-xs text-[var(--color-ink-faint)]">{ev.company_name}</span>
								{/if}
							</div>
							<div
								class="flex shrink-0 items-center gap-1 whitespace-nowrap text-xs text-[var(--color-ink-faint)]"
							>
								<Clock size={12} aria-hidden="true" />
								<time class="ci-mono" datetime={ev.created_at}>{formatTime(ev.created_at)}</time>
							</div>
						</li>
					{/each}
				</ul>
			</section>
		</div>
	{/if}
</div>
