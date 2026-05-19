<script lang="ts">
  import { BarChart3, Activity, Zap, DollarSign } from "lucide-svelte";

  let { title, value, change = "", icon = "chart" }: {
    title: string;
    value: string | number;
    change?: string;
    icon?: "chart" | "activity" | "zap" | "dollar";
  } = $props();

  const icons = { chart: BarChart3, activity: Activity, zap: Zap, dollar: DollarSign };
  let Icon = $derived(icons[icon]);
</script>

<div class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
  <div class="flex items-center justify-between">
    <div>
      <p class="text-sm font-medium text-slate-500 dark:text-slate-400">{title}</p>
      <p class="mt-1 text-2xl font-semibold text-slate-900 dark:text-slate-100">{value}</p>
      {#if change}
        <p class="mt-0.5 text-xs text-emerald-600 dark:text-emerald-400">{change}</p>
      {/if}
    </div>
    <div class="rounded-lg bg-slate-100 p-2.5 dark:bg-slate-800">
      <Icon size={20} class="text-slate-600 dark:text-slate-300" />
    </div>
  </div>
</div>
