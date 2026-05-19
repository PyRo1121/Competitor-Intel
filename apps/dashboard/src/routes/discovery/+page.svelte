<script lang="ts">
	import { onMount } from "svelte";
	import { getDiscoveryCandidates, getTopScored, type DiscoveryCandidate } from "$lib/api";
	import PageHeader from "$lib/components/PageHeader.svelte";

	let candidates = $state<DiscoveryCandidate[]>([]);
	let topScored = $state<{ name: string; score: number | null; slug?: string | null }[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);

	onMount(async () => {
		try {
			const [pending, ranked] = await Promise.all([
				getDiscoveryCandidates(50),
				getTopScored(10),
			]);
			candidates = pending.candidates ?? [];
			topScored = (ranked.companies ?? []).map((c) => ({
				name: c.name,
				score: c.score ?? null,
				slug: c.slug,
			}));
		} catch (e) {
			error = e instanceof Error ? e.message : "Failed to load discovery";
			console.error(e);
		} finally {
			loading = false;
		}
	});

	function formatScore(v: number | null | undefined): string {
		if (v == null || Number.isNaN(Number(v))) return "—";
		return Number(v).toFixed(2);
	}
</script>

<div class="ci-page">
	<PageHeader
		title="Discovery"
		subtitle="Pending names from the signal firehose and top promoted companies by attention score."
	/>

	{#if error}
		<div class="ci-alert-error mb-6" role="alert">{error}</div>
	{/if}

	{#if loading}
		<div class="grid gap-6 lg:grid-cols-2">
			<div class="ci-skeleton h-64"></div>
			<div class="ci-skeleton h-64"></div>
		</div>
	{:else}
		<div class="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
			{#each topScored as row, i}
				<div class="ci-panel p-4">
					<p class="text-xs text-[var(--color-ink-faint)]">#{i + 1}</p>
					{#if row.slug}
						<a href={`/companies/${row.slug}`} class="ci-link mt-1 block font-medium">{row.name}</a>
					{:else}
						<p class="mt-1 font-medium text-[var(--color-ink)]">{row.name}</p>
					{/if}
					<p class="ci-mono mt-2 text-lg tabular-nums text-[var(--color-accent-bright)]">
						{formatScore(row.score)}
					</p>
				</div>
			{/each}
		</div>

		<div class="ci-panel ci-table-wrap">
			<h2 class="border-b border-[var(--color-border)] px-4 py-3 text-sm font-semibold uppercase tracking-wider text-[var(--color-ink-muted)]">
				Pending candidates ({candidates.length})
			</h2>
			<table class="ci-table">
				<thead>
					<tr>
						<th>Name</th>
						<th>Score</th>
						<th>Signals</th>
						<th>Source</th>
						<th>Updated</th>
					</tr>
				</thead>
				<tbody>
					{#each candidates as c}
						<tr>
							<td class="font-medium text-[var(--color-ink)]">{c.name}</td>
							<td class="ci-mono text-sm">{formatScore(c.score)}</td>
							<td class="ci-mono text-sm text-[var(--color-ink-muted)]">{c.signals ?? "—"}</td>
							<td class="text-sm text-[var(--color-ink-muted)]">{c.discovery_source ?? "—"}</td>
							<td class="text-xs text-[var(--color-ink-faint)]">
								{c.last_updated ? new Date(c.last_updated).toLocaleString() : "—"}
							</td>
						</tr>
					{:else}
						<tr>
							<td colspan="5" class="py-8 text-center text-[var(--color-ink-faint)]">
								No pending candidates — run discover + promote in the worker pipeline.
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>
