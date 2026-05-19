<script lang="ts">
  import { onMount } from "svelte";
  import { getStatus } from "$lib/api";
  import { Activity, Database, Bell } from "lucide-svelte";

  let status: any = $state(null);

  onMount(async () => {
    try {
      status = await getStatus();
    } catch (e) {
      console.error(e);
    }
  });
</script>

<div class="p-8 max-w-3xl mx-auto">
  <h1 class="text-2xl font-semibold text-slate-900 dark:text-slate-100 mb-8">Settings</h1>

  <div class="space-y-6">
    <div class="rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
      <div class="flex items-center gap-3 mb-4">
        <Activity size={20} class="text-slate-500" />
        <h2 class="text-sm font-semibold text-slate-900 dark:text-slate-100">API Status</h2>
      </div>
      {#if status}
        <div class="flex items-center gap-2">
          <div class="h-2.5 w-2.5 rounded-full bg-emerald-500"></div>
          <span class="text-sm text-slate-600 dark:text-slate-300">Connected</span>
          <span class="text-xs text-slate-400 dark:text-slate-500">{status.counts.companies} companies tracked</span>
        </div>
      {:else}
        <div class="flex items-center gap-2">
          <div class="h-2.5 w-2.5 rounded-full bg-red-500"></div>
          <span class="text-sm text-slate-600 dark:text-slate-300">Disconnected</span>
        </div>
      {/if}
    </div>

    <div class="rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
      <div class="flex items-center gap-3 mb-4">
        <Database size={20} class="text-slate-500" />
        <h2 class="text-sm font-semibold text-slate-900 dark:text-slate-100">Data Sources</h2>
      </div>
      <div class="space-y-2 text-sm">
        <div class="flex justify-between"><span class="text-slate-600 dark:text-slate-300">RSS Feeds</span><span class="text-slate-900 dark:text-slate-100">87</span></div>
        <div class="flex justify-between"><span class="text-slate-600 dark:text-slate-300">X/Twitter Queries</span><span class="text-slate-900 dark:text-slate-100">43</span></div>
        <div class="flex justify-between"><span class="text-slate-600 dark:text-slate-300">YouTube Channels</span><span class="text-slate-900 dark:text-slate-100">10</span></div>
      </div>
    </div>

    <div class="rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
      <div class="flex items-center gap-3 mb-4">
        <Bell size={20} class="text-slate-500" />
        <h2 class="text-sm font-semibold text-slate-900 dark:text-slate-100">Notifications</h2>
      </div>
      <div class="space-y-3">
        <label class="flex items-center justify-between cursor-pointer">
          <span class="text-sm text-slate-600 dark:text-slate-300">Funding alerts</span>
          <input type="checkbox" checked class="rounded border-slate-300 text-amber-500 focus:ring-amber-500" />
        </label>
        <label class="flex items-center justify-between cursor-pointer">
          <span class="text-sm text-slate-600 dark:text-slate-300">Product launches</span>
          <input type="checkbox" checked class="rounded border-slate-300 text-amber-500 focus:ring-amber-500" />
        </label>
        <label class="flex items-center justify-between cursor-pointer">
          <span class="text-sm text-slate-600 dark:text-slate-300">Acquisitions</span>
          <input type="checkbox" checked class="rounded border-slate-300 text-amber-500 focus:ring-amber-500" />
        </label>
      </div>
    </div>
  </div>
</div>
