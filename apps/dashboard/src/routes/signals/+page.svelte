<script lang="ts">
  import { onMount } from "svelte";
  import { getSignals } from "$lib/api";
  import SearchBar from "$lib/components/SearchBar.svelte";
  import { Clock } from "lucide-svelte";

  let signals: any[] = $state([]);
  let loading = $state(true);

  onMount(async () => {
    try {
      const res = await getSignals({ limit: 100 });
      signals = res.signals || [];
    } catch (e) {
      console.error(e);
    } finally {
      loading = false;
    }
  });

  function sourceColor(source: string) {
    const map: Record<string, string> = {
      rss: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
      hackernews: "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300",
      producthunt: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
      youtube: "bg-rose-100 text-rose-700 dark:bg-rose-900 dark:text-rose-300",
      github: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
    };
    return map[source] || "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300";
  }
</script>

<div class="p-8 max-w-7xl mx-auto">
  <div class="flex items-center justify-between mb-8">
    <div>
      <h1 class="text-2xl font-semibold text-slate-900 dark:text-slate-100">Signals</h1>
      <p class="text-sm text-slate-500 dark:text-slate-400 mt-1">Raw intelligence feeds</p>
    </div>
    <SearchBar />
  </div>

  {#if loading}
    <div class="space-y-3">
      {#each [1, 2, 3, 4, 5] as _}
        <div class="h-20 bg-slate-100 animate-pulse rounded-xl dark:bg-slate-800"></div>
      {/each}
    </div>
  {:else}
    <div class="space-y-3">
      {#each signals as signal}
        <div class="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
          <div class="flex items-start justify-between gap-4">
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-1">
                <span class="inline-flex rounded-full px-2 py-0.5 text-xs font-medium {sourceColor(signal.source)}">
                  {signal.source}
                </span>
                <span class="text-xs text-slate-400 dark:text-slate-500">{signal.signal_label || signal.signal_type}</span>
                {#if signal.company_name}
                  <span class="text-xs text-slate-500 dark:text-slate-400">{signal.company_name}</span>
                {/if}
              </div>
              <p class="text-sm text-slate-700 dark:text-slate-300 line-clamp-2">
                {JSON.parse(signal.data_json || "{}").title || signal.data_json?.slice(0, 200) || "No title"}
              </p>
            </div>
            <div class="flex items-center gap-1 text-xs text-slate-400 dark:text-slate-500 whitespace-nowrap">
              <Clock size={12} />
              {signal.detected_at?.slice(0, 16).replace("T", " ") || "—"}
            </div>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
