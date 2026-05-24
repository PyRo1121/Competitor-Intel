<script lang="ts">
	import { page } from "$app/stores";
	import { createQuery } from "@tanstack/svelte-query";
	import { getJobPosting } from "$lib/api";
	import { formatSeniority, formatUsd, truncate } from "$lib/format";
	import type { JobPostingDetailResponse } from "$lib/types/structured-intel";
	import CorroborationBadge from "$lib/components/CorroborationBadge.svelte";
	import { ArrowLeft } from "lucide-svelte";

	const id = $derived($page.params.id ?? "");

	const jobQuery = createQuery(() => ({
		queryKey: ["job-posting", id],
		queryFn: () => getJobPosting(id) as Promise<JobPostingDetailResponse>,
		enabled: Boolean(id),
	}));

	const data = $derived(jobQuery.data);
</script>

<div class="ci-page max-w-5xl">
	<a href="/jobs" class="ci-btn mb-6">
		<ArrowLeft size={16} aria-hidden="true" />
		Back to Jobs
	</a>

	{#if jobQuery.isPending}
		<div class="ci-skeleton h-40"></div>
	{:else if jobQuery.isError}
		<div class="ci-alert-error" role="alert">{jobQuery.error?.message ?? "Failed to load posting"}</div>
	{:else if data}
		{@const posting = data.posting}
		<header class="ci-panel-glow mb-8 p-6">
			<h1 class="ci-display text-2xl font-semibold">{posting.title}</h1>
			<p class="text-sm text-[var(--color-ink-muted)] mt-1">
				<a href="/companies/{posting.company_slug ?? posting.company_id}" class="ci-link">
					{posting.company_name}
				</a>
				{#if posting.posted_at}
					· Posted {posting.posted_at}
				{/if}
			</p>
			<div class="flex flex-wrap gap-3 mt-4 text-sm text-[var(--color-ink-muted)]">
				<span>{formatSeniority(posting.seniority_band)}</span>
				{#if posting.location}<span>{posting.location}</span>{/if}
				{#if posting.remote_policy}<span>{posting.remote_policy}</span>{/if}
				{#if posting.ats_platform}<span>{posting.ats_platform}</span>{/if}
			</div>
			<div class="mt-3 flex items-center gap-3">
				<CorroborationBadge
					score={posting.corroboration_score}
					reportCount={posting.report_count}
					size="md"
				/>
				{#if posting.salary_min_usd != null || posting.salary_max_usd != null}
					<span class="text-sm tabular-nums font-medium ci-mono">
						{formatUsd(posting.salary_min_usd)} – {formatUsd(posting.salary_max_usd)}
					</span>
				{/if}
			</div>
		</header>

		{#if data.skills.length > 0}
			<section class="mb-10" aria-labelledby="skills-heading">
				<h2 id="skills-heading" class="text-sm font-semibold mb-3">
					Skills ({data.skills.length})
				</h2>
				<div class="flex flex-wrap gap-2">
					{#each data.skills as skill (skill.skill)}
						<span class="ci-badge border border-[var(--color-border)] bg-[var(--color-surface-2)]">
							{skill.skill}
							{#if skill.mention_count && skill.mention_count > 1}
								<span class="text-[var(--color-ink-faint)] ml-1">×{skill.mention_count}</span>
							{/if}
						</span>
					{/each}
				</div>
			</section>
		{/if}

		<section aria-labelledby="claims-heading">
			<h2 id="claims-heading" class="text-sm font-semibold mb-4">
				Source claims ({data.claims.length})
			</h2>
			{#if data.claims.length === 0}
				<p class="text-sm text-[var(--color-ink-faint)]">No linked claims.</p>
			{:else}
				<ul class="space-y-3" role="list">
					{#each data.claims as claim (claim.id)}
						<li class="ci-panel p-4">
							<p class="font-medium">{claim.title ?? "Untitled"}</p>
							{#if claim.skills?.length}
								<p class="text-xs text-[var(--color-ink-faint)] mt-2">
									{claim.skills.map((s) => s.skill).join(", ")}
								</p>
							{/if}
							<a
								href={claim.source_url}
								target="_blank"
								rel="noopener noreferrer"
								class="ci-link text-xs mt-2 inline-block"
							>
								View source
							</a>
						</li>
					{/each}
				</ul>
			{/if}
		</section>
	{:else}
		<p class="text-[var(--color-ink-faint)]">Posting not found</p>
	{/if}
</div>
