<script lang="ts">
	import { Search } from "lucide-svelte";
	import { goto } from "$app/navigation";

	let query = $state("");

	async function onSubmit(e: Event) {
		e.preventDefault();
		if (!query.trim()) return;
		await goto(`/search?q=${encodeURIComponent(query)}`);
	}
</script>

<form onsubmit={onSubmit} class="relative w-full max-w-md">
	<Search size={16} class="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-ink-faint)]" />
	<input
		bind:value={query}
		placeholder="Search companies, events, signals…"
		class="w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] py-2.5 pl-10 pr-4 text-sm text-[var(--color-ink)] placeholder-[var(--color-ink-faint)] transition-colors focus:border-[var(--color-accent)] focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)]/50"
	/>
</form>
