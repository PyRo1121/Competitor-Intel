<script lang="ts">
  import { onMount } from "svelte";
  import { getSignals, type SignalRecord } from "$lib/api";
  import { parseSignalPreview } from "$lib/freshness";
  import SearchBar from "$lib/components/SearchBar.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import { Clock } from "lucide-svelte";

  let signals = $state<SignalRecord[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  onMount(async () => {
    try {
      const res = await getSignals({ limit: 100 });
      signals = res.signals || [];
    } catch (e) {
      error = e instanceof Error ? e.message : "Failed to load signals";
      console.error(e);
    } finally {
      loading = false;
    }
  });

  function sourceColor(source: string) {
    const map: Record<string, string> = {
      rss: "border-[var(--color-accent)]/30 text-[var(--color-accent-bright)] bg-[var(--color-cyan-dim)]",
      hackernews: "border-[var(--color-warning)]/30 text-[var(--color-warning)] bg-[rgba(251,191,36,0.12)]",
      producthunt: "border-[var(--color-coral)]/30 text-[var(--color-coral)] bg-[rgba(251,113,133,0.12)]",
      youtube: "border-[var(--color-magenta)]/30 text-[var(--color-magenta)] bg-[var(--color-magenta-dim)]",
      github: "border-[var(--color-border)] text-[var(--color-ink-muted)] bg-[var(--color-surface-2)]",
    };
    return (
      map[source] ??
      "border-[var(--color-border)] text-[var(--color-ink-muted)] bg-[var(--color-surface-2)]"
    );
  }
</script>

<div class="ci-page">
  <PageHeader title="Signals" subtitle="Raw intelligence feeds">
    {#snippet actions()}
      <SearchBar />
    {/snippet}
  </PageHeader>

  {#if error}
    <div class="ci-alert-error mb-6" role="alert">{error}</div>
  {:else if loading}
    <div class="space-y-3">
      {#each [1, 2, 3, 4, 5] as _}
        <div class="ci-skeleton h-20"></div>
      {/each}
    </div>
  {:else}
    <div class="space-y-3">
      {#each signals as signal}
        <div class="ci-panel p-5">
          <div class="flex items-start justify-between gap-4">
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-1">
                <span class="ci-badge border {sourceColor(signal.source)}">
                  {signal.source}
                </span>
                <span class="text-xs text-[var(--color-ink-faint)]">{signal.signal_label || signal.signal_type}</span>
                {#if signal.company_name}
                  <span class="text-xs text-[var(--color-ink-muted)]">{signal.company_name}</span>
                {/if}
              </div>
              <p class="text-sm text-[var(--color-ink-muted)] line-clamp-2">
                {parseSignalPreview(signal.data_json)}
              </p>
            </div>
            <div class="flex items-center gap-1 text-xs text-[var(--color-ink-faint)] whitespace-nowrap">
              <Clock size={12} />
              {signal.detected_at?.slice(0, 16).replace("T", " ") || "—"}
            </div>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
