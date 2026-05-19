<script lang="ts">
  import { Search } from "lucide-svelte";
  import { goto } from "$app/navigation";

  let query = $state("");

  async function onSubmit(e: Event) {
    e.preventDefault();
    if (!query.trim()) return;
    await goto(`/search?q=${encodeURIComponent(query)}`);
  }
</script>

<form onsubmit={onSubmit} class="relative w-full max-w-md">
  <Search size={16} class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
  <input
    bind:value={query}
    placeholder="Search companies, events, signals..."
    class="w-full rounded-lg border border-slate-200 bg-white py-2.5 pl-10 pr-4 text-sm text-slate-900 placeholder-slate-400 focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
  />
</form>
