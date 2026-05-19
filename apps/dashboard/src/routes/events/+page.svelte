<script lang="ts">
  import { onMount } from "svelte";
  import { getEvents } from "$lib/api";
  import SearchBar from "$lib/components/SearchBar.svelte";
  import { TrendingUp, AlertCircle, Zap } from "lucide-svelte";

  let events: any[] = $state([]);
  let loading = $state(true);

  onMount(async () => {
    try {
      const res = await getEvents({ limit: 100 });
      events = res.events || [];
    } catch (e) {
      console.error(e);
    } finally {
      loading = false;
    }
  });

  function eventIcon(type: string) {
    if (type?.includes("funding")) return TrendingUp;
    if (type?.includes("acquisition")) return AlertCircle;
    return Zap;
  }

  function eventColor(type: string) {
    if (type?.includes("funding")) return "text-emerald-500";
    if (type?.includes("acquisition")) return "text-amber-500";
    if (type?.includes("launch")) return "text-blue-500";
    return "text-slate-400";
  }
</script>

<div class="p-8 max-w-7xl mx-auto">
  <div class="flex items-center justify-between mb-8">
    <div>
      <h1 class="text-2xl font-semibold text-slate-900 dark:text-slate-100">Events</h1>
      <p class="text-sm text-slate-500 dark:text-slate-400 mt-1">Intelligence events</p>
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
      {#each events as event}
        {@const Icon = eventIcon(event.event_type)}
        <div class="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
          <div class="flex items-start gap-4">
            <div class="mt-0.5 {eventColor(event.event_type)}">
              <Icon size={18} />
            </div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-1">
                <span class="font-medium text-slate-900 dark:text-slate-100">{event.company_name || "Unknown"}</span>
                <span class="text-slate-400 dark:text-slate-500">—</span>
                <span class="text-sm text-slate-600 dark:text-slate-300">{event.event_type}</span>
              </div>
              {#if event.amount_usd}
                <p class="text-sm text-emerald-600 dark:text-emerald-400 font-medium">${(event.amount_usd / 1_000_000).toFixed(1)}M</p>
              {/if}
            </div>
            <span class="text-xs text-slate-400 dark:text-slate-500 whitespace-nowrap">
              {event.created_at?.slice(0, 16).replace("T", " ") || "—"}
            </span>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
