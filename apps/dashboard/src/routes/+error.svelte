<script lang="ts">
	import { page } from "$app/stores";

	let { error } = $props();
	const message = $derived(
		error?.message ??
			($page.error as { message?: string } | null)?.message ??
			"Something went wrong loading this page.",
	);
	const status = $derived(($page.status as number) || 500);
</script>

<div class="ci-page max-w-lg">
	<h1 class="ci-display text-2xl font-semibold text-[var(--color-ink)] mb-2">
		{status === 404 ? "Page not found" : "Unexpected error"}
	</h1>
	<p class="text-sm text-[var(--color-ink-muted)] mb-6">{message}</p>
	<a href="/" class="ci-btn-primary inline-block">Back to dashboard</a>
</div>
