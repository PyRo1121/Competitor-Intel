<script lang="ts">
  import { onMount } from "svelte";
  import { getCompanies } from "$lib/api";
  import SearchBar from "$lib/components/SearchBar.svelte";
  import { ArrowUpRight, Star } from "lucide-svelte";

  let companies: any[] = $state([]);
  let loading = $state(true);

  onMount(async () => {
    try {
      const res = await getCompanies();
      companies = res.companies || [];
    } catch (e) {
      console.error(e);
    } finally {
      loading = false;
    }
  });

  function statusClass(status: string) {
    const map: Record<string, string> = {
      active: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300",
      acquired: "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300",
      dead: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
      pivoted: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
    };
    return map[status] || map.active;
  }
</script>

<div class="p-8 max-w-7xl mx-auto">
  <div class="flex items-center justify-between mb-8">
    <div>
      <h1 class="text-2xl font-semibold text-slate-900 dark:text-slate-100">Companies</h1>
      <p class="text-sm text-slate-500 dark:text-slate-400 mt-1">{companies.length} companies tracked</p>
    </div>
    <SearchBar />
  </div>

  {#if loading}
    <div class="space-y-3">
      {#each [1, 2, 3, 4, 5] as _}
        <div class="h-16 rounded-xl bg-slate-100 animate-pulse dark:bg-slate-800"></div>
      {/each}
    </div>
  {:else}
    <div class="rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900 overflow-hidden">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-slate-100 dark:border-slate-800">
            <th class="px-6 py-3 text-left font-medium text-slate-500 dark:text-slate-400">Company</th>
            <th class="px-6 py-3 text-left font-medium text-slate-500 dark:text-slate-400">Industry</th>
            <th class="px-6 py-3 text-left font-medium text-slate-500 dark:text-slate-400">Status</th>
            <th class="px-6 py-3 text-left font-medium text-slate-500 dark:text-slate-400">Links</th>
          </tr>
        </thead>
        <tbody>
          {#each companies as company}
            <tr class="border-b border-slate-50 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/50 transition-colors">
              <td class="px-6 py-4">
                <a href={`/companies/${company.id}`} class="font-medium text-slate-900 hover:text-amber-600 dark:text-slate-100 dark:hover:text-amber-400 transition-colors">
                  {company.name}
                </a>
                {#if company.slug}
                  <p class="text-xs text-slate-400 dark:text-slate-500">@{company.slug}</p>
                {/if}
              </td>
              <td class="px-6 py-4 text-slate-600 dark:text-slate-300">{company.industry || "—"}</td>
              <td class="px-6 py-4">
                <span class="inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium {statusClass(company.status)}">
                  {company.status}
                </span>
              </td>
              <td class="px-6 py-4">
                <div class="flex items-center gap-3">
                  {#if company.website}
                    <a href={company.website} target="_blank" rel="noopener" class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors">
                      <ArrowUpRight size={16} />
                    </a>
                  {/if}
                  {#if company.github_org}
                    <a href={`https://github.com/${company.github_org}`} target="_blank" rel="noopener" class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors">
                      <Star size={16} />
                    </a>
                  {/if}
                </div>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
