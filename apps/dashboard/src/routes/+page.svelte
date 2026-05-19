<script lang="ts">
  import { onMount } from "svelte";
  import { getStatus } from "$lib/api";
  import StatCard from "$lib/components/StatCard.svelte";
  import { Building2, Radio, Activity, Wallet, Clock } from "lucide-svelte";

  let status = $state<{
    counts: { companies: number; signals: number; events: number; funding: number; xPosts: number };
    last24h: { signals: number; events: number };
    topSources: { source: string; count: number }[];
    recentEvents: { event_type: string; company_name: string | null; amount_usd: number | null; created_at: string }[];
  } | null>(null);

  onMount(async () => {
    try {
      status = await getStatus();
    } catch (e) {
      console.error(e);
    }
  });

  function formatTime(iso: string) {
    if (!iso) return "—";
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  function eventLabel(type: string) {
    return type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  }
</script>

<div class="p-8 max-w-7xl mx-auto">
  <div class="mb-8">
    <h1 class="text-2xl font-semibold text-slate-900 dark:text-slate-100">Dashboard</h1>
    <p class="text-sm text-slate-500 dark:text-slate-400 mt-1">Competitor intelligence overview</p>
  </div>

  {#if !status}
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {#each [1, 2, 3, 4] as _}
        <div class="h-24 rounded-xl bg-slate-100 animate-pulse dark:bg-slate-800"></div>
      {/each}
    </div>
  {:else}
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
      <StatCard title="Companies" value={status.counts.companies} icon="chart" />
      <StatCard title="Signals" value={status.counts.signals} change={`${status.last24h.signals} in 24h`} icon="activity" />
      <StatCard title="Events" value={status.counts.events} change={`${status.last24h.events} in 24h`} icon="zap" />
      <StatCard title="Funding" value={status.counts.funding} icon="dollar" />
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div class="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
        <h2 class="text-sm font-medium text-slate-500 dark:text-slate-400 mb-4">Top Sources</h2>
        <div class="space-y-3">
          {#each status.topSources as src}
            <div class="flex items-center justify-between">
              <span class="text-sm text-slate-700 dark:text-slate-300">{src.source}</span>
              <span class="text-sm font-medium text-slate-900 dark:text-slate-100">{src.count}</span>
            </div>
          {/each}
        </div>
      </div>

      <div class="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
        <h2 class="text-sm font-medium text-slate-500 dark:text-slate-400 mb-4">Recent Events</h2>
        <div class="space-y-3">
          {#each status.recentEvents as ev}
            <div class="flex items-center justify-between">
              <div>
                <span class="text-sm font-medium text-slate-700 dark:text-slate-300">{eventLabel(ev.event_type)}</span>
                {#if ev.company_name}
                  <span class="text-xs text-slate-400 dark:text-slate-500 ml-2">{ev.company_name}</span>
                {/if}
              </div>
              <div class="flex items-center gap-1 text-xs text-slate-400 dark:text-slate-500">
                <Clock size={12} />
                {formatTime(ev.created_at)}
              </div>
            </div>
          {/each}
        </div>
      </div>
    </div>
  {/if}
</div>
