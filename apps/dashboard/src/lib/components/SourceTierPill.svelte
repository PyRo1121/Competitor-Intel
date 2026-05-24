<script lang="ts">
	import { formatSourceTier } from "$lib/format";

	let {
		tier,
		official = false,
	}: {
		tier: string | null | undefined;
		official?: boolean | number | null;
	} = $props();

	const label = $derived(
		official ? "Official" : formatSourceTier(tier),
	);

	const tone = $derived.by(() => {
		if (official) return "official";
		const t = (tier ?? "").toLowerCase();
		if (t.includes("company") || t.includes("official")) return "official";
		if (t.includes("tier_1") || t === "press_wire") return "tier1";
		if (t.includes("social")) return "social";
		return "default";
	});

	const classes: Record<string, string> = {
		official: "border-[var(--color-magenta)]/30 text-[var(--color-magenta)] bg-[var(--color-magenta-dim)]",
		tier1: "border-[var(--color-accent)]/30 text-[var(--color-accent-bright)] bg-[var(--color-cyan-dim)]",
		social: "border-[var(--color-accent-bright)]/25 text-[var(--color-accent-bright)] bg-[var(--color-cyan-dim)]",
		default: "border-[var(--color-border)] text-[var(--color-ink-muted)] bg-[var(--color-surface-2)]",
	};
</script>

<span class="ci-badge border {classes[tone]}">
	{label}
</span>
