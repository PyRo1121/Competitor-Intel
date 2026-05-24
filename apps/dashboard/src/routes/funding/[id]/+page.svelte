<script lang="ts">
	import { page } from "$app/stores";
	import { createQuery } from "@tanstack/svelte-query";
	import { getFundingRound } from "$lib/api";
	import { formatUsd, truncate } from "$lib/format";
	import type { FundingRoundDetailResponse } from "$lib/types/structured-intel";
	import CorroborationBadge from "$lib/components/CorroborationBadge.svelte";
	import SourceTierPill from "$lib/components/SourceTierPill.svelte";
	import { ArrowLeft, ExternalLink } from "lucide-svelte";

	const id = $derived($page.params.id ?? "");

	const roundQuery = createQuery(() => ({
		queryKey: ["funding-round", id],
		queryFn: () => getFundingRound(id) as Promise<FundingRoundDetailResponse>,
		enabled: Boolean(id),
	}));

	const data = $derived(roundQuery.data);
</script>

<div class="ci-page max-w-5xl">
	<a href="/funding" class="ci-btn mb-6">
		<ArrowLeft size={16} aria-hidden="true" />
		Back to Funding
	</a>

	{#if roundQuery.isPending}
		<div class="ci-skeleton h-40"></div>
	{:else if roundQuery.isError}
		<div class="ci-alert-error" role="alert">{roundQuery.error?.message ?? "Failed to load round"}</div>
	{:else if data}
		{@const round = data.round}
		<header class="ci-panel-glow mb-8 p-6">
			<div class="flex flex-wrap items-start justify-between gap-4">
				<div>
					<h1 class="ci-display text-2xl font-semibold">
						{round.company_name ?? "Company"}
						{#if round.round_type}
							<span class="text-[var(--color-ink-muted)] font-normal"> · {round.round_type}</span>
						{/if}
					</h1>
					<p class="text-sm text-[var(--color-ink-muted)] mt-1">
						{round.announced_date ?? "Date unknown"}
						{#if round.instrument_type && round.instrument_type !== "equity"}
							· {round.instrument_type}
						{/if}
					</p>
				</div>
				<div class="text-right">
					<p class="text-2xl font-semibold tabular-nums ci-mono">{formatUsd(round.amount_usd)}</p>
					<div class="mt-2 flex justify-end">
						<CorroborationBadge
							score={round.corroboration_score}
							officialCount={round.official_report_count}
							reportCount={round.report_count}
							size="md"
						/>
					</div>
				</div>
			</div>
			{#if round.company_website}
				<a
					href={round.company_website}
					target="_blank"
					rel="noopener noreferrer"
					class="ci-link inline-flex items-center gap-1 text-sm mt-3"
				>
					{round.company_website}
					<ExternalLink size={14} aria-hidden="true" />
				</a>
			{/if}
			{#if round.lead_investor}
				<p class="text-sm text-[var(--color-ink-muted)] mt-2">
					Lead: <span class="font-medium text-[var(--color-ink)]">{round.lead_investor}</span>
				</p>
			{/if}
		</header>

		<section class="mb-10" aria-labelledby="participants-heading">
			<h2 id="participants-heading" class="text-sm font-semibold mb-4">
				Canonical investors ({data.participants.length})
			</h2>
			{#if data.participants.length === 0}
				<p class="text-sm text-[var(--color-ink-faint)]">No merged investor attributions yet.</p>
			{:else}
				<ul class="space-y-3" role="list">
					{#each data.participants as p (p.id)}
						<li class="ci-panel p-4">
							<div class="flex flex-wrap items-center justify-between gap-2">
								<div>
									<span class="font-medium">{p.investor_name ?? "Unknown"}</span>
									{#if p.is_lead}
										<span class="ml-2 text-xs font-medium text-[var(--color-cyan)]">Lead</span>
									{/if}
									{#if p.investor_tier === 1}
										<span class="ml-1 text-xs text-[var(--color-healthy)]">Tier 1</span>
									{/if}
								</div>
								<CorroborationBadge score={p.corroboration_score} size="sm" />
							</div>
							{#if p.source_attributions?.length}
								<ul class="mt-3 space-y-1 text-xs text-[var(--color-ink-faint)] border-t border-[var(--color-border)] pt-3">
									{#each p.source_attributions as attr}
										{@const a = attr as { headline?: string; source_tier?: string; source_url?: string }}
										<li class="flex flex-wrap items-center gap-2">
											<SourceTierPill tier={a.source_tier} />
											<span>{truncate(a.headline, 80) || a.source_url}</span>
										</li>
									{/each}
								</ul>
							{/if}
						</li>
					{/each}
				</ul>
			{/if}
		</section>

		<section aria-labelledby="claims-heading">
			<h2 id="claims-heading" class="text-sm font-semibold mb-4">
				Source claims ({data.claims.length})
			</h2>
			{#if data.claims.length === 0}
				<p class="text-sm text-[var(--color-ink-faint)]">No linked claims for this round.</p>
			{:else}
				<ul class="space-y-3" role="list">
					{#each data.claims as claim (claim.id)}
						<li class="ci-panel p-4">
							<div class="flex flex-wrap items-center gap-2 mb-2">
								<SourceTierPill tier={claim.source_tier} official={claim.is_official} />
								<span class="text-sm font-medium tabular-nums ci-mono">{formatUsd(claim.amount_usd)}</span>
							</div>
							<p class="text-sm text-[var(--color-ink-muted)]">
								{truncate(claim.headline ?? claim.snippet, 200) || "—"}
							</p>
							<a
								href={claim.source_url}
								target="_blank"
								rel="noopener noreferrer"
								class="ci-link text-xs mt-2 inline-block"
							>
								View source
							</a>
							{#if claim.participants?.length}
								<p class="text-xs text-[var(--color-ink-faint)] mt-2">
									Investors on this claim:
									{claim.participants.map((x) => x.investor_name).filter(Boolean).join(", ")}
								</p>
							{/if}
						</li>
					{/each}
				</ul>
			{/if}
		</section>
	{:else}
		<p class="text-[var(--color-ink-faint)]">Round not found</p>
	{/if}
</div>
