<script lang="ts">
	import { formatPercent } from "$lib/format";
	import { corroborationLabel } from "$lib/provenance";

	let {
		score,
		officialCount = 0,
		reportCount = null,
		size = "sm",
		/** When true, show confidence tier label; score % stays in title. */
		labeled = false,
	}: {
		score: number | null | undefined;
		officialCount?: number | null;
		reportCount?: number | null;
		size?: "sm" | "md";
		labeled?: boolean;
	} = $props();

	const label = $derived(corroborationLabel(score));

	const level = $derived.by(() => {
		if (score == null) return "muted";
		if (score >= 0.75) return "high";
		if (score >= 0.45) return "mid";
		return "low";
	});

	const classes = $derived({
		high: "border border-[var(--color-healthy)]/30 text-[var(--color-healthy)] bg-[rgba(52,211,153,0.1)]",
		mid: "border border-[var(--color-cyan)]/30 text-[var(--color-cyan)] bg-[var(--color-cyan-dim)]",
		low: "border border-[var(--color-border)] text-[var(--color-ink-muted)] bg-[var(--color-surface-2)]",
		muted: "border border-[var(--color-border)] text-[var(--color-ink-faint)] bg-[var(--color-base)]",
	});

	const pad = $derived(size === "md" ? "px-2.5 py-1 text-xs" : "px-2 py-0.5 text-[0.65rem]");
</script>

<span
	class="inline-flex items-center gap-1 rounded-full font-semibold tabular-nums {pad} {classes[level]}"
	title={reportCount != null ? `${reportCount} source reports · ${formatPercent(score)}` : formatPercent(score)}
>
	{#if labeled}
		{label}
	{:else}
		{formatPercent(score)}
	{/if}
	{#if officialCount && officialCount > 0}
		<span class="font-normal opacity-80">· official</span>
	{/if}
</span>
