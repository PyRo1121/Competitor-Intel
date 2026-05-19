<script lang="ts">
  import { page } from "$app/stores";
  import { onMount } from "svelte";
  import { search } from "$lib/api";
  import { Search, Building2, Calendar, Radio } from "lucide-svelte";

  let query = $derived($page.url.searchParams.get("q") || "");
  let data: any = $state(null);
  let loading = $state(false);

  onMount(() => { if (query) doSearch(); });

  async function doSearch() {
    if (!query.trim()) return;
    loading = true;
    try {
      data = await search(query);
    } catch (e) {
      console.error(e);
    } finally {
      loading = false;
    }
  }
</script>

<div class="p-8 max-w-5xl mx-auto">
  <h1 class="text-2xl font-semibold text-slate-900 dark:text-slate-100 mb-6">Search</h1>

  <div class="relative mb-8">
    <Search size={16} class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
    <input
      bind:value={query}
      placeholder="Search companies, events, signals..."
      class="w-full rounded-lg border border-slate-200 bg-white py-3 pl-10 pr-4 text-slate-900 placeholder-slate-400 focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
    />
  </div>

  {#if loading}
    <div class="space-y-3">
      {#each [1, 2, 3] as _}
        <div class="h-16 bg-slate-100 animate-pulse rounded-xl dark:bg-slate-800"></div>
      {/each}
    </div>
  {:else if data}
    {#if data.companies?.length > 0}
      <div class="mb-8">
        <h2 class="text-sm font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-3">Companies</h2>
        <div class="space-y-2">
          {#each data.companies as company}
            <a href={`/companies/${company.id}`} class="flex items-center gap-3 rounded-lg border border-slate-200 bg-white p-4 hover:border-amber-300 dark:border-slate-800 dark:bg-slate-900 dark:hover:border-amber-700 transition-colors">
              <Building2 size={18} class="text-slate-400" />
              <div>
                <p class="font-medium text-slate-900 dark:text-slate-100">{company.name}</p>
                <p class="text-xs text-slate-500 dark:text-slate-400">{company.industry || "Technology"}</p>
              </div>
            </a>
          {/each}
        </div>
      </div>
    {/if}

    {#if data.events?.length > 0}
      <div class="mb-8">
        <h2 class="text-sm font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-3">Events</h2>
        <div class="space-y-2">
          {#each data.events as event}
            <div class="flex items-center gap-3 rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
              <Calendar size={18} class="text-slate-400" />
              <div>
                <p class="font-medium text-slate-900 dark:text-slate-100">{event.company_name || "Unknown"}</p>
                <p class="text-xs text-slate-500 dark:text-slate-400">{event.event_type}</p>
              </div>
            </div>
          {/each}
        </div>
      </div>
    {/if}

    {#if data.signals?.length > 0}
      <div class="mb-8">
        <h2 class="text-sm font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-3">Signals</h2>
        <div class="space-y-2">
          {#each data.signals as signal}
            <div class="flex items-center gap-3 rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
              <Radio size={18} class="text-slate-400" />
              <div>
                <p class="text-sm text-slate-700 dark:text-slate-300">{signal.source} {signal.signal_label || signal.signal_type}</p>
                <p class="text-xs text-slate-400 dark:text-slate-500">{signal.detected_at?.slice(0, 16)}</p>
              </div>
            </div>
          {/each}
        </div>
      </div>
    {/if}

    {#if !data.companies?.length && !data.events?.length && !data.signals?.length}
      <p class="text-slate-500 dark:text-slate-400 text-center py-12">No results for "{query}"</p>
    {/if}
  {/if}
</div>
