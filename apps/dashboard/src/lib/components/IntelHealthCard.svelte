<script lang="ts">
	import { buildIngestHealth, levelTone } from "$lib/freshness";
	import type { StatusResponse } from "$lib/types/status";
	import { Activity, MessageCircle, Radio, Wallet } from "lucide-svelte";

	let {
		status,
		apiReachable = true,
	}: {
		status: StatusResponse;
		apiReachable?: boolean;
	} = $props();

	const health = $derived(buildIngestHealth(status, apiReachable));
	const overallTone = $derived(levelTone(health.pipelineOverall ?? health.overall));

	const icons = {
		lastSignalAt: Radio,
		lastEventAt: Activity,
		lastXAt: MessageCircle,
	} as const;
</script>

<article class="ci-panel overflow-hidden border {overallTone.border}" aria-labelledby="intel-health-heading">
	<div class="ci-panel-header flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between {overallTone.bg}">
		<div>
			<h2 id="intel-health-heading" class="ci-display text-lg font-medium text-[var(--color-ink)]">
				Ingest health
			</h2>
			<p class="mt-1 max-w-xl text-xs leading-relaxed text-[var(--color-ink-muted)]">
				Pipeline health uses RSS + events only. X verification is shown separately and does not mark ingest stale.
				See docs/SCHEDULING.md.
			</p>
		</div>
		<span class="ci-badge border bg-[var(--color-surface)] {overallTone.border} {overallTone.text}">
			<span class="mr-1.5 h-1.5 w-1.5 rounded-full {overallTone.dot}" aria-hidden="true"></span>
			{overallTone.label}
		</span>
	</div>

	<ul class="grid gap-3 p-5 sm:grid-cols-3" role="list">
		{#each health.metrics as metric (metric.key)}
			{@const tone = levelTone(metric.level)}
			{@const Icon = icons[metric.key]}
			<li class="rounded-xl border border-[var(--color-border-subtle)] bg-[var(--color-canvas)] p-4">
				<div class="mb-2 flex items-center gap-2">
					<Icon size={16} class="text-[var(--color-accent)]" aria-hidden="true" />
					<span class="text-xs font-medium text-[var(--color-ink-muted)]">{metric.label}</span>
				</div>
				<p class="ci-display text-xl font-medium text-[var(--color-ink)]">
					<time datetime={metric.at ?? undefined} title={metric.absoluteLabel}>
						{metric.relativeLabel}
					</time>
				</p>
				<p class="ci-mono mt-1 text-[0.65rem] text-[var(--color-ink-faint)]">{metric.absoluteLabel}</p>
				<p class="mt-2 text-xs font-semibold uppercase tracking-wide {tone.text}">{tone.label}</p>
			</li>
		{/each}
	</ul>

	<footer
		class="flex flex-wrap gap-4 border-t border-[var(--color-border-subtle)] px-5 py-4 text-xs text-[var(--color-ink-muted)]"
	>
		<span>
			<span class="font-medium text-[var(--color-ink)]">24h volume:</span>
			<span class="ci-mono">{status.last24h.signals}</span> signals ·
			<span class="ci-mono">{status.last24h.events}</span> events
		</span>
		<span>
			<span class="font-medium text-[var(--color-ink)]">Corpus:</span>
			<span class="ci-mono">{status.counts.signals.toLocaleString()}</span> signals ·
			<span class="ci-mono">{status.counts.xPosts.toLocaleString()}</span> X posts
		</span>
		{#if status.counts.funding > 0}
			<span class="inline-flex items-center gap-1">
				<Wallet size={12} class="text-[var(--color-accent)]" aria-hidden="true" />
				<span class="ci-mono">{status.counts.funding.toLocaleString()}</span> funding rounds
			</span>
		{/if}
		{#if (status.counts.pendingCandidates ?? 0) > 0}
			<a href="/discovery" class="ci-link">
				<span class="font-medium text-[var(--color-ink)]">Discovery queue:</span>
				<span class="ci-mono">{status.counts.pendingCandidates}</span> pending
			</a>
		{/if}
	</footer>
</article>
