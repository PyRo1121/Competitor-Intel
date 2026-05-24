<script lang="ts">
	/** Per-item confidence for feeds — rises as source noise / corroboration increases. */
	let {
		label = "Early signal",
		size = "sm",
	}: {
		label?: "Early signal" | "Building" | "Strong";
		size?: "sm" | "md";
	} = $props();

	const tone = $derived(
		label === "Strong"
			? "border-[var(--color-healthy)]/30 text-[var(--color-healthy)] bg-[rgba(52,211,153,0.1)]"
			: label === "Building"
				? "border-amber-500/30 text-amber-200 bg-amber-500/10"
				: "border-[var(--color-border)] text-[var(--color-ink-faint)] bg-[var(--color-surface-2)]",
	);

	const pad = $derived(size === "md" ? "px-2.5 py-1 text-xs" : "px-2 py-0.5 text-[0.65rem]");
</script>

<span class="inline-flex rounded-full border font-semibold uppercase tracking-wide {pad} {tone}">
	{label}
</span>
