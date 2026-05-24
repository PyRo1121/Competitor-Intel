<script lang="ts">
	import { createQuery } from "@tanstack/svelte-query";
	import { getCompanies } from "$lib/api";
	import SearchBar from "$lib/components/SearchBar.svelte";
	import PageHeader from "$lib/components/PageHeader.svelte";
	import { ArrowUpRight, Star } from "lucide-svelte";

	const companiesQuery = createQuery(() => ({
		queryKey: ["companies", "score"],
		queryFn: () => getCompanies("score"),
	}));

	const companies = $derived(companiesQuery.data?.companies ?? []);

	function statusClass(status: string) {
		const map: Record<string, string> = {
			active: "bg-[rgba(61,214,140,0.12)] text-[var(--color-healthy)] border-[var(--color-healthy)]/20",
			acquired: "bg-[var(--color-accent-muted)] text-[var(--color-accent-bright)] border-[var(--color-accent)]/20",
			dead: "bg-[rgba(240,113,120,0.1)] text-[var(--color-stale)] border-[var(--color-stale)]/20",
			pivoted: "bg-[var(--color-surface-hover)] text-[var(--color-ink-muted)] border-[var(--color-border)]",
		};
		return map[status] || map.active;
	}
</script>

<div class="ci-page">
	<PageHeader title="Companies" subtitle={`${companies.length} tracked — sorted by attention score.`}>
		{#snippet actions()}
			<SearchBar />
		{/snippet}
	</PageHeader>

	{#if companiesQuery.isPending}
		<div class="space-y-3">
			{#each [1, 2, 3, 4, 5] as _}
				<div class="ci-skeleton h-16"></div>
			{/each}
		</div>
	{:else}
		<div class="ci-panel ci-table-wrap">
			<table class="ci-table">
				<thead>
					<tr>
						<th>Company</th>
						<th>Score</th>
						<th>Industry</th>
						<th>Status</th>
						<th>Links</th>
					</tr>
				</thead>
				<tbody>
					{#each companies as company}
						<tr>
							<td>
								<a href={`/companies/${String(company.slug ?? company.id)}`} class="ci-link font-medium">
									{String(company.name ?? "—")}
								</a>
								{#if company.slug}
									<p class="ci-mono text-xs text-[var(--color-ink-faint)]">@{String(company.slug)}</p>
								{/if}
							</td>
							<td class="ci-mono text-sm text-[var(--color-ink-muted)]">
								{company.score != null ? Number(company.score).toFixed(2) : "—"}
							</td>
							<td class="text-[var(--color-ink-muted)]">{String(company.industry ?? "—")}</td>
							<td>
								<span class="ci-badge border {statusClass(String(company.status ?? "active"))}">{String(company.status ?? "—")}</span>
							</td>
							<td>
								<div class="flex items-center gap-3">
									{#if company.website}
										<a
											href={String(company.website)}
											target="_blank"
											rel="noopener"
											class="text-[var(--color-ink-faint)] hover:text-[var(--color-accent)]"
										>
											<ArrowUpRight size={16} />
										</a>
									{/if}
									{#if company.is_priority}
										<Star size={16} class="fill-[var(--color-accent)] text-[var(--color-accent)]" />
									{/if}
								</div>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>
