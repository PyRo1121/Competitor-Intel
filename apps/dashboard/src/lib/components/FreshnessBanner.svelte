<script lang="ts">
	import { buildIngestHealth, levelTone } from "$lib/freshness";
	import type { StatusResponse } from "$lib/types/status";
	import { RefreshCw } from "lucide-svelte";

	let {
		status = null,
		apiReachable = true,
		loading = false,
		onRefresh = undefined,
	}: {
		status: StatusResponse | null;
		apiReachable?: boolean;
		loading?: boolean;
		onRefresh?: () => void;
	} = $props();

	const health = $derived(buildIngestHealth(status, apiReachable));
	const overallTone = $derived(levelTone(health.pipelineOverall ?? health.overall));
</script>

<section
	class="sticky top-0 z-30 border-b border-[var(--color-border-subtle)] bg-[var(--color-canvas-elevated)]/90 backdrop-blur-md"
	aria-label="Data freshness"
	role="status"
>
	<div
		class="mx-auto flex max-w-7xl flex-col gap-2 px-5 py-2.5 sm:flex-row sm:items-center sm:justify-between lg:px-8"
	>
		<div class="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-1.5">
			{#if !apiReachable}
				<span class="inline-flex items-center gap-2 text-sm font-medium text-[var(--color-stale)]">
					<span class="h-2 w-2 shrink-0 rounded-full bg-[var(--color-stale)]" aria-hidden="true"></span>
					API unreachable
				</span>
			{:else if loading && !status}
				<span class="text-sm text-[var(--color-ink-muted)]">Loading ingest status…</span>
			{:else}
				<span
					class="ci-badge border {overallTone.bg} {overallTone.border} {overallTone.text}"
				>
					<span class="mr-1.5 h-1.5 w-1.5 shrink-0 rounded-full {overallTone.dot}" aria-hidden="true"></span>
					Ingest {overallTone.label.toLowerCase()}
				</span>

				{#each health.metrics as metric (metric.key)}
					{@const tone = levelTone(metric.level)}
					<span class="inline-flex items-center gap-1.5 text-xs text-[var(--color-ink-muted)]">
						<span class="h-1.5 w-1.5 shrink-0 rounded-full {tone.dot}" aria-hidden="true"></span>
						<span class="font-medium text-[var(--color-ink)]">{metric.shortLabel}</span>
						<time class="ci-mono" datetime={metric.at ?? undefined} title={metric.absoluteLabel}>
							{metric.relativeLabel}
						</time>
					</span>
				{/each}
			{/if}
		</div>

		<div class="flex shrink-0 items-center gap-3 text-xs text-[var(--color-ink-faint)]">
			{#if status}
				<span class="hidden md:inline ci-mono" title="Last 24 hours">
					{status.last24h.signals} signals · {status.last24h.events} events (24h)
				</span>
			{/if}
			{#if onRefresh}
				<button type="button" class="ci-btn" onclick={onRefresh} disabled={loading} aria-label="Refresh ingest status">
					<RefreshCw size={14} class={loading ? "animate-spin" : ""} />
					Refresh
				</button>
			{/if}
		</div>
	</div>
</section>
