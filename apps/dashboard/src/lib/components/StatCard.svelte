<script lang="ts">
	import { BarChart3, Activity, Zap, DollarSign } from "lucide-svelte";

	let {
		title,
		value,
		change = "",
		icon = "chart",
	}: {
		title: string;
		value: string | number;
		change?: string;
		icon?: "chart" | "activity" | "zap" | "dollar";
	} = $props();

	const icons = { chart: BarChart3, activity: Activity, zap: Zap, dollar: DollarSign };
	const Icon = $derived(icons[icon]);
</script>

<div class="ci-panel group p-5 transition-colors hover:border-[var(--color-accent)]/30">
	<div class="flex items-start justify-between gap-4">
		<div class="min-w-0">
			<p class="text-xs font-semibold uppercase tracking-wider text-[var(--color-ink-faint)]">{title}</p>
			<p class="ci-display mt-2 text-3xl font-medium tabular-nums text-[var(--color-ink)]">{value}</p>
			{#if change}
				<p class="mt-1 text-xs text-[var(--color-healthy)]">{change}</p>
			{/if}
		</div>
		<div
			class="rounded-xl border border-[var(--color-border-subtle)] bg-[var(--color-surface-hover)] p-2.5 text-[var(--color-accent)] transition-colors group-hover:border-[var(--color-accent)]/40 group-hover:bg-[var(--color-accent-muted)]"
		>
			<Icon size={20} aria-hidden="true" />
		</div>
	</div>
</div>
