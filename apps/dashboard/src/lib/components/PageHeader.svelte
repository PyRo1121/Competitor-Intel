<script lang="ts">
	import type { Snippet } from "svelte";

	let {
		title,
		subtitle = "",
		actions,
	}: {
		title: string;
		subtitle?: string;
		actions?: Snippet;
	} = $props();
</script>

<header class="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
	<div>
		<p class="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--color-accent)] mb-2">
			Intelligence
		</p>
		<h1 class="ci-display text-3xl sm:text-4xl font-medium text-[var(--color-ink)]">{title}</h1>
		{#if subtitle}
			<p class="mt-2 max-w-2xl text-sm leading-relaxed text-[var(--color-ink-muted)]">{subtitle}</p>
		{/if}
	</div>
	{#if actions}
		<div class="flex shrink-0 items-center gap-3">
			{@render actions()}
		</div>
	{/if}
</header>
