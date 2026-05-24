<script lang="ts">
	import { createQuery } from "@tanstack/svelte-query";
	import {
		getFunding,
		getFundingClaims,
		getFundingInvestors,
	} from "$lib/api";
	import { formatUsd, truncate } from "$lib/format";
	import type {
		FundingClaimRow,
		FundingListResponse,
		InvestorFirmRow,
	} from "$lib/types/structured-intel";
	import CorroborationBadge from "$lib/components/CorroborationBadge.svelte";
	import SourceTierPill from "$lib/components/SourceTierPill.svelte";
	import EmptyState from "$lib/components/EmptyState.svelte";
	import SearchBar from "$lib/components/SearchBar.svelte";
	import PageHeader from "$lib/components/PageHeader.svelte";
	import { DollarSign, FileText, Users } from "lucide-svelte";

	type View = "rounds" | "claims" | "investors";

	let view = $state<View>("rounds");

	const fundingQuery = createQuery(() => ({
		queryKey: ["funding", "list"],
		queryFn: () => getFunding() as Promise<FundingListResponse>,
	}));

	const claimsQuery = createQuery(() => ({
		queryKey: ["funding", "claims"],
		queryFn: async () => {
			const res = await getFundingClaims({ limit: 150 });
			return res.claims as FundingClaimRow[];
		},
	}));

	const investorsQuery = createQuery(() => ({
		queryKey: ["funding", "investors"],
		queryFn: async () => {
			const res = await getFundingInvestors({ limit: 100 });
			return res.investors as InvestorFirmRow[];
		},
	}));

	const list = $derived(fundingQuery.data ?? null);
	const claims = $derived(claimsQuery.data ?? []);
	const investors = $derived(investorsQuery.data ?? []);
	const loading = $derived(
		fundingQuery.isPending || claimsQuery.isPending || investorsQuery.isPending,
	);
	const error = $derived(
		fundingQuery.error?.message ??
			claimsQuery.error?.message ??
			investorsQuery.error?.message ??
			null,
	);

	const tabs: { id: View; label: string; icon: typeof DollarSign }[] = [
		{ id: "rounds", label: "Canonical rounds", icon: DollarSign },
		{ id: "claims", label: "Source claims", icon: FileText },
		{ id: "investors", label: "Investors", icon: Users },
	];
</script>

<div class="ci-page">
	<PageHeader
		title="Funding"
		subtitle="Per-outlet claims merge into canonical rounds with investor attributions and corroboration scores."
	>
		{#snippet actions()}
			<SearchBar />
		{/snippet}
	</PageHeader>

	{#if error}
		<div class="ci-alert-error mb-6" role="alert">{error}</div>
	{/if}

	{#if list && !loading}
		<div class="mb-8 grid grid-cols-2 gap-4 lg:grid-cols-4">
			{#each [
				{ label: "Canonical rounds", value: list.stats.total_rounds },
				{ label: "Source claims", value: list.stats.total_claims },
				{ label: "Investor firms", value: list.stats.investor_firms },
				{ label: "Total disclosed", value: formatUsd(list.stats.total_raised) },
			] as stat}
				<div class="ci-panel p-4">
					<p class="text-xs font-semibold uppercase tracking-wider text-[var(--color-ink-faint)]">{stat.label}</p>
					<p class="ci-display mt-1 text-xl font-medium tabular-nums text-[var(--color-ink)]">{stat.value}</p>
				</div>
			{/each}
		</div>
	{/if}

	<nav class="mb-6 flex gap-1 border-b border-[var(--color-border-subtle)]" aria-label="Funding views">
		{#each tabs as tab}
			<button
				type="button"
				onclick={() => (view = tab.id)}
				class="ci-tab {view === tab.id ? 'ci-tab-active' : ''}"
			>
				<tab.icon size={16} aria-hidden="true" />
				{tab.label}
			</button>
		{/each}
	</nav>

	{#if loading}
		<div class="ci-skeleton h-64"></div>
	{:else if view === "rounds" && list}
		{#if list.funding.length === 0}
			<EmptyState
				title="No canonical rounds yet"
				description="Run make funding-rollup after signal_processor to merge claims into funding_rounds."
			/>
		{:else}
			<div class="ci-panel ci-table-wrap">
				<table class="ci-table min-w-[720px]">
					<thead>
						<tr>
							<th>Company</th>
							<th>Round</th>
							<th>Amount</th>
							<th>Date</th>
							<th>Corroboration</th>
							<th>Sources</th>
						</tr>
					</thead>
					<tbody>
						{#each list.funding as round (round.id)}
							<tr>
								<td class="font-medium">
									<a href="/funding/{round.id}" class="ci-link">{round.company_name ?? "—"}</a>
								</td>
								<td class="text-[var(--color-ink-muted)]">{round.round_type ?? "—"}</td>
								<td class="tabular-nums">{formatUsd(round.amount_usd)}</td>
								<td class="text-[var(--color-ink-muted)]">{round.announced_date ?? "—"}</td>
								<td>
									<CorroborationBadge
										score={round.corroboration_score}
										officialCount={round.official_report_count}
										reportCount={round.report_count}
									/>
								</td>
								<td class="tabular-nums text-[var(--color-ink-muted)]">
									{round.claim_count ?? round.report_count ?? "—"}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{:else if view === "claims"}
		{#if claims.length === 0}
			<EmptyState title="No funding claims" description="Claims are created from funding intelligence events and RSS deal coverage." />
		{:else}
			<ul class="space-y-3" role="list">
				{#each claims as claim (claim.id)}
					<li class="ci-panel p-4">
						<div class="flex flex-wrap items-start justify-between gap-3">
							<div class="min-w-0 flex-1">
								<div class="mb-1 flex flex-wrap items-center gap-2">
									<span class="font-medium text-[var(--color-ink)]">{claim.company_name}</span>
									<SourceTierPill tier={claim.source_tier} official={claim.is_official} />
									{#if claim.round_type}
										<span class="text-xs text-[var(--color-ink-muted)]">{claim.round_type}</span>
									{/if}
								</div>
								<p class="text-sm text-[var(--color-ink-muted)]">
									{truncate(claim.headline ?? claim.snippet, 160) || "—"}
								</p>
								<a
									href={claim.source_url}
									target="_blank"
									rel="noopener noreferrer"
									class="ci-link mt-1 inline-block max-w-full truncate text-xs"
								>
									{claim.source_url}
								</a>
							</div>
							<div class="shrink-0 text-right">
								<p class="text-sm font-semibold tabular-nums text-[var(--color-ink)]">{formatUsd(claim.amount_usd)}</p>
								{#if claim.participants?.length}
									<p class="mt-1 text-xs text-[var(--color-ink-faint)]">
										{claim.participants.length} investor{claim.participants.length === 1 ? "" : "s"} named
									</p>
								{/if}
							</div>
						</div>
					</li>
				{/each}
			</ul>
		{/if}
	{:else if view === "investors"}
		{#if investors.length === 0}
			<EmptyState title="No investor firms" description="Investors appear after claims are parsed or Hermes funding enrich is applied." />
		{:else}
			<div class="ci-panel ci-table-wrap">
				<table class="ci-table">
					<thead>
						<tr>
							<th>Firm</th>
							<th>Tier</th>
							<th>Rounds</th>
							<th>Claim mentions</th>
						</tr>
					</thead>
					<tbody>
						{#each investors as inv (inv.id)}
							<tr>
								<td class="font-medium text-[var(--color-ink)]">{inv.name}</td>
								<td class="text-[var(--color-ink-muted)]">
									{inv.tier != null ? `Tier ${inv.tier}` : "—"}
								</td>
								<td class="tabular-nums">{inv.round_count ?? 0}</td>
								<td class="tabular-nums">{inv.claim_mention_count ?? 0}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{/if}
</div>
