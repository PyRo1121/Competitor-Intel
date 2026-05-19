<script lang="ts">
  import { page } from "$app/stores";
  import { onMount } from "svelte";
  import { getCompany } from "$lib/api";
  import { ArrowLeft, ExternalLink, GitBranch } from "lucide-svelte";

  let id = $derived($page.params.id);
  let data: any = $state(null);
  let loading = $state(true);
  let activeTab = $state("overview");
  const tabs = ["overview", "funding", "tech"];

  onMount(async () => {
    if (!id) return;
    try {
      data = await getCompany(id);
    } catch (e) {
      console.error(e);
    } finally {
      loading = false;
    }
  });
</script>

<div class="p-8 max-w-5xl mx-auto">
  {#if loading}
    <div class="space-y-4">
      <div class="h-8 w-48 bg-slate-100 animate-pulse rounded dark:bg-slate-800"></div>
      <div class="h-32 bg-slate-100 animate-pulse rounded-xl dark:bg-slate-800"></div>
    </div>
  {:else if data}
    <div class="mb-6">
      <a href="/companies" class="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100 transition-colors mb-4">
        <ArrowLeft size={16} />
        Back to Companies
      </a>
      <div class="flex items-start justify-between">
        <div>
          <h1 class="text-2xl font-semibold text-slate-900 dark:text-slate-100">{data.company.name}</h1>
          <p class="text-sm text-slate-500 dark:text-slate-400 mt-1">{data.company.industry || "AI / Technology"}</p>
        </div>
        <div class="flex items-center gap-2">
          {#if data.company.website}
            <a href={data.company.website} target="_blank" rel="noopener" class="rounded-lg border border-slate-200 p-2 text-slate-500 hover:border-slate-300 hover:text-slate-900 dark:border-slate-700 dark:text-slate-400 dark:hover:border-slate-600 dark:hover:text-slate-100 transition-colors">
              <ExternalLink size={18} />
            </a>
          {/if}
          {#if data.company.github_org}
            <a href={`https://github.com/${data.company.github_org}`} target="_blank" rel="noopener" class="rounded-lg border border-slate-200 p-2 text-slate-500 hover:border-slate-300 hover:text-slate-900 dark:border-slate-700 dark:text-slate-400 dark:hover:border-slate-600 dark:hover:text-slate-100 transition-colors">
              <GitBranch size={18} />
            </a>
          {/if}
        </div>
      </div>
    </div>

    <div class="border-b border-slate-200 dark:border-slate-800 mb-6">
      <nav class="flex gap-6">
        {#each tabs as tab}
          <button
            onclick={() => activeTab = tab}
            class="pb-3 text-sm font-medium capitalize transition-colors border-b-2 -mb-px
              {activeTab === tab
                ? 'border-amber-500 text-slate-900 dark:text-slate-100'
                : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300'}"
          >
            {tab}
          </button>
        {/each}
      </nav>
    </div>

    {#if activeTab === "overview"}
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        {#if data.details}
          <div class="rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
            <h3 class="text-sm font-semibold text-slate-900 dark:text-slate-100 mb-4">Company Details</h3>
            <dl class="space-y-3 text-sm">
              {#if data.details.founded_year}
                <div class="flex justify-between"><dt class="text-slate-500 dark:text-slate-400">Founded</dt><dd class="text-slate-900 dark:text-slate-100">{data.details.founded_year}</dd></div>
              {/if}
              {#if data.details.headquarters}
                <div class="flex justify-between"><dt class="text-slate-500 dark:text-slate-400">HQ</dt><dd class="text-slate-900 dark:text-slate-100">{data.details.headquarters}</dd></div>
              {/if}
              {#if data.details.team_size}
                <div class="flex justify-between"><dt class="text-slate-500 dark:text-slate-400">Team Size</dt><dd class="text-slate-900 dark:text-slate-100">{data.details.team_size}</dd></div>
              {/if}
              {#if data.details.business_model}
                <div class="flex justify-between"><dt class="text-slate-500 dark:text-slate-400">Model</dt><dd class="text-slate-900 dark:text-slate-100">{data.details.business_model}</dd></div>
              {/if}
            </dl>
          </div>
        {/if}
        {#if data.github}
          <div class="rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
            <h3 class="text-sm font-semibold text-slate-900 dark:text-slate-100 mb-4">GitHub Metrics</h3>
            <dl class="space-y-3 text-sm">
              <div class="flex justify-between"><dt class="text-slate-500 dark:text-slate-400">Total Commits</dt><dd class="text-slate-900 dark:text-slate-100">{data.github.total_commits?.toLocaleString() || "—"}</dd></div>
              <div class="flex justify-between"><dt class="text-slate-500 dark:text-slate-400">Contributors</dt><dd class="text-slate-900 dark:text-slate-100">{data.github.contributor_count || "—"}</dd></div>
              <div class="flex justify-between"><dt class="text-slate-500 dark:text-slate-400">Primary Language</dt><dd class="text-slate-900 dark:text-slate-100">{data.github.primary_language || "—"}</dd></div>
            </dl>
          </div>
        {/if}
      </div>
    {:else if activeTab === "funding"}
      {#if data.funding?.length > 0}
        <div class="rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900 overflow-hidden">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-slate-100 dark:border-slate-800">
                <th class="px-6 py-3 text-left font-medium text-slate-500 dark:text-slate-400">Round</th>
                <th class="px-6 py-3 text-left font-medium text-slate-500 dark:text-slate-400">Amount</th>
                <th class="px-6 py-3 text-left font-medium text-slate-500 dark:text-slate-400">Date</th>
                <th class="px-6 py-3 text-left font-medium text-slate-500 dark:text-slate-400">Lead</th>
              </tr>
            </thead>
            <tbody>
              {#each data.funding as round}
                <tr class="border-b border-slate-50 dark:border-slate-800">
                  <td class="px-6 py-4 font-medium text-slate-900 dark:text-slate-100">{round.round_type}</td>
                  <td class="px-6 py-4 text-slate-600 dark:text-slate-300">{round.amount_usd ? `$${(round.amount_usd / 1_000_000).toFixed(1)}M` : "Undisclosed"}</td>
                  <td class="px-6 py-4 text-slate-500 dark:text-slate-400">{round.announced_date || "—"}</td>
                  <td class="px-6 py-4 text-slate-600 dark:text-slate-300">{round.lead_investor || "—"}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {:else}
        <p class="text-slate-500 dark:text-slate-400">No funding data available</p>
      {/if}
    {:else if activeTab === "tech"}
      {#if data.tech_stack?.length > 0}
        <div class="flex flex-wrap gap-2">
          {#each data.tech_stack as tech}
            <span class="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-300">
              {tech.technology}
              <span class="text-slate-400 dark:text-slate-500 ml-1">{Math.round(tech.confidence * 100)}%</span>
            </span>
          {/each}
        </div>
      {:else}
        <p class="text-slate-500 dark:text-slate-400">No tech stack data</p>
      {/if}
    {/if}
  {:else}
    <p class="text-slate-500 dark:text-slate-400">Company not found</p>
  {/if}
</div>
