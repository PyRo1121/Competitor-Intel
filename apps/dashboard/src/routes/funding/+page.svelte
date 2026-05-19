<script lang="ts">
  import { onMount } from "svelte";
  import { getFunding } from "$lib/api";
  import SearchBar from "$lib/components/SearchBar.svelte";
  import { DollarSign, TrendingUp } from "lucide-svelte";

  let data: any = $state(null);
  let loading = $state(true);

  onMount(async () => {
    try {
      data = await getFunding();
    } catch (e) {
      console.error(e);
    } finally {
      loading = false;
    }
  });
</script>

<div class="p-8 max-w-7xl mx-auto">
  <div class="flex items-center justify-between mb-8">
    <div>
      <h1 class="text-2xl font-semibold text-slate-900 dark:text-slate-100">Funding</h1>
      <p class="text-sm text-slate-500 dark:text-slate-400 mt-1">Funding rounds and deal flow</p>
    </div>
    <SearchBar />
  </div>

  {#if loading}
    <div class="space-y-4">
      <div class="h-24 bg-slate-100 animate-pulse rounded-xl dark:bg-slate-800"></div>
      <div class="h-64 bg-slate-100 animate-pulse rounded-xl dark:bg-slate-800"></div>
    </div>
  {:else if data}
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
      <div class="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
        <div class="flex items-center gap-3">
          <div class="rounded-lg bg-emerald-100 p-2 dark:bg-emerald-900">
            <DollarSign size={20} class="text-emerald-600 dark:text-emerald-400" />
          </div>
          <div>
            <p class="text-sm text-slate-500 dark:text-slate-400">Total Raised</p>
            <p class="text-xl font-semibold text-slate-900 dark:text-slate-100">${((data.stats.total_raised || 0) / 1_000_000_000).toFixed(2)}B</p>
          </div>
        </div>
      </div>
      <div class="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
        <div class="flex items-center gap-3">
          <div class="rounded-lg bg-amber-100 p-2 dark:bg-amber-900">
            <TrendingUp size={20} class="text-amber-600 dark:text-amber-400" />
          </div>
          <div>
            <p class="text-sm text-slate-500 dark:text-slate-400">Rounds</p>
            <p class="text-xl font-semibold text-slate-900 dark:text-slate-100">{data.stats.total_rounds}</p>
          </div>
        </div>
      </div>
      <div class="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
        <div class="flex items-center gap-3">
          <div class="rounded-lg bg-blue-100 p-2 dark:bg-blue-900">
            <DollarSign size={20} class="text-blue-600 dark:text-blue-400" />
          </div>
          <div>
            <p class="text-sm text-slate-500 dark:text-slate-400">Avg Round</p>
            <p class="text-xl font-semibold text-slate-900 dark:text-slate-100">${((data.stats.avg_round || 0) / 1_000_000).toFixed(1)}M</p>
          </div>
        </div>
      </div>
    </div>

    <div class="rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900 overflow-hidden">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-slate-100 dark:border-slate-800">
            <th class="px-6 py-3 text-left font-medium text-slate-500 dark:text-slate-400">Company</th>
            <th class="px-6 py-3 text-left font-medium text-slate-500 dark:text-slate-400">Round</th>
            <th class="px-6 py-3 text-left font-medium text-slate-500 dark:text-slate-400">Amount</th>
            <th class="px-6 py-3 text-left font-medium text-slate-500 dark:text-slate-400">Date</th>
            <th class="px-6 py-3 text-left font-medium text-slate-500 dark:text-slate-400">Lead</th>
          </tr>
        </thead>
        <tbody>
          {#each data.funding as round}
            <tr class="border-b border-slate-50 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/50 transition-colors">
              <td class="px-6 py-4 font-medium text-slate-900 dark:text-slate-100">{round.company_name || "—"}</td>
              <td class="px-6 py-4 text-slate-600 dark:text-slate-300">{round.round_type}</td>
              <td class="px-6 py-4 text-slate-900 dark:text-slate-100 font-medium">{round.amount_usd ? `$${(round.amount_usd / 1_000_000).toFixed(1)}M` : "Undisclosed"}</td>
              <td class="px-6 py-4 text-slate-500 dark:text-slate-400">{round.announced_date || "—"}</td>
              <td class="px-6 py-4 text-slate-600 dark:text-slate-300">{round.lead_investor || "—"}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {:else}
    <p class="text-slate-500 dark:text-slate-400">Failed to load funding data</p>
  {/if}
</div>
