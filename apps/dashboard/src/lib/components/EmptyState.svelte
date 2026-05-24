<script lang="ts">
	let {
		title,
		description,
	}: {
		title: string;
		description?: string;
	} = $props();
</script>

<div
	class="rounded-2xl border border-dashed border-[var(--color-border)] bg-[var(--color-surface)]/50 px-6 py-14 text-center"
	role="status"
>
	<p class="ci-display text-lg font-medium text-[var(--color-ink-muted)]">{title}</p>
	{#if description}
		<p class="mx-auto mt-2 max-w-md text-sm leading-relaxed text-[var(--color-ink-faint)]">{description}</p>
	{/if}
</div>
