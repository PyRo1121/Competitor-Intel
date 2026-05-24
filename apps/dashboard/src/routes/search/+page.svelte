<script lang="ts">
  import { page } from "$app/stores";
  import { goto } from "$app/navigation";
  import { search, type SearchMode } from "$lib/api";
  import { Search, Building2, Calendar, Radio } from "lucide-svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";

  interface SearchCompany {
    id: number;
    name: string;
    slug?: string | null;
    industry?: string | null;
    score?: number | null;
  }

  interface SearchSignal {
    source?: string;
    signal_label?: string;
    signal_type?: string;
    detected_at?: string;
  }

  interface SearchEvent {
    company_name?: string;
    event_type?: string;
  }

  interface SearchPayload {
    mode?: string;
    companies?: SearchCompany[];
    events?: SearchEvent[];
    signals?: SearchSignal[];
  }

  let query = $state("");
  let mode = $state<SearchMode>("keyword");
  let data = $state<SearchPayload | null>(null);
  let loading = $state(false);
  let error = $state<string | null>(null);
  let lastFetchedKey = $state("");

  const modes: { id: SearchMode; label: string }[] = [
    { id: "keyword", label: "Keyword" },
    { id: "auto", label: "Auto" },
    { id: "semantic", label: "Semantic" },
  ];

  $effect(() => {
    const urlQ = $page.url.searchParams.get("q") ?? "";
    const urlMode = ($page.url.searchParams.get("mode") ?? "keyword") as SearchMode;
    if (urlQ !== query) query = urlQ;
    if (modes.some((m) => m.id === urlMode) && urlMode !== mode) mode = urlMode;
    const key = `${urlQ}|${mode}`;
    if (urlQ && key !== lastFetchedKey) {
      void runSearch(urlQ, mode);
    }
  });

  function companyHref(company: SearchCompany): string {
    const segment = company.slug?.trim() || String(company.id);
    return `/companies/${segment}`;
  }

  async function runSearch(q: string, searchMode: SearchMode) {
    const trimmed = q.trim();
    if (!trimmed) {
      data = null;
      lastFetchedKey = "";
      error = null;
      return;
    }
    loading = true;
    error = null;
    try {
      data = (await search(trimmed, searchMode)) as SearchPayload;
      lastFetchedKey = `${trimmed}|${searchMode}`;
    } catch (e) {
      error = e instanceof Error ? e.message : "Search failed";
      console.error(e);
      data = null;
    } finally {
      loading = false;
    }
  }

  async function onSubmit(e: Event) {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;
    const params = new URLSearchParams($page.url.searchParams);
    params.set("q", trimmed);
    params.set("mode", mode);
    await goto(`/search?${params}`, { keepFocus: true, noScroll: true });
    await runSearch(trimmed, mode);
  }
</script>

<div class="ci-page max-w-5xl">
  <PageHeader title="Search" subtitle="Keyword, auto-routed, or semantic lookup across companies, events, and signals." />

  <form class="mb-4 flex flex-wrap items-center gap-3" onsubmit={onSubmit}>
    <div class="relative min-w-[16rem] flex-1">
      <Search size={16} class="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-ink-faint)]" />
      <input
        bind:value={query}
        placeholder="Search companies, events, signals..."
        class="ci-field py-3 pl-10 pr-4"
      />
    </div>
    <select bind:value={mode} class="ci-field w-auto px-3 py-3" aria-label="Search mode">
      {#each modes as m}
        <option value={m.id}>{m.label}</option>
      {/each}
    </select>
    <button type="submit" class="ci-btn-primary">Search</button>
  </form>

  {#if error}
    <div class="ci-alert-error mb-6" role="alert">{error}</div>
  {/if}

  {#if loading}
    <div class="space-y-3">
      {#each [1, 2, 3] as _}
        <div class="ci-skeleton h-16"></div>
      {/each}
    </div>
  {:else if data}
    {#if data.mode}
      <p class="text-xs text-[var(--color-ink-muted)] mb-4">
        Search mode: <span class="font-medium text-[var(--color-ink)]">{data.mode}</span>
      </p>
    {/if}

    {#if data.companies?.length}
      <div class="mb-8">
        <h2 class="text-sm font-semibold text-[var(--color-ink-faint)] uppercase tracking-wide mb-3">Companies</h2>
        <div class="space-y-2">
          {#each data.companies as company}
            <a
              href={companyHref(company)}
              class="ci-panel flex items-center gap-3 p-4 transition-colors hover:border-[var(--color-accent)]"
            >
              <Building2 size={18} class="text-[var(--color-ink-faint)]" />
              <div>
                <p class="font-medium text-[var(--color-ink)]">
                  {company.name}
                  {#if company.score != null}
                    <span class="ml-2 text-xs font-normal text-[var(--color-accent)]">
                      {Number(company.score).toFixed(2)}
                    </span>
                  {/if}
                </p>
                <p class="text-xs text-[var(--color-ink-muted)]">{company.industry || "Technology"}</p>
              </div>
            </a>
          {/each}
        </div>
      </div>
    {/if}

    {#if data.events?.length}
      <div class="mb-8">
        <h2 class="text-sm font-semibold text-[var(--color-ink-faint)] uppercase tracking-wide mb-3">Events</h2>
        <div class="space-y-2">
          {#each data.events as event}
            <div class="ci-panel flex items-center gap-3 p-4">
              <Calendar size={18} class="text-[var(--color-ink-faint)]" />
              <div>
                <p class="font-medium text-[var(--color-ink)]">{event.company_name || "Unknown"}</p>
                <p class="text-xs text-[var(--color-ink-muted)]">{event.event_type}</p>
              </div>
            </div>
          {/each}
        </div>
      </div>
    {/if}

    {#if data.signals?.length}
      <div class="mb-8">
        <h2 class="text-sm font-semibold text-[var(--color-ink-faint)] uppercase tracking-wide mb-3">Signals</h2>
        <div class="space-y-2">
          {#each data.signals as signal}
            <div class="ci-panel flex items-center gap-3 p-4">
              <Radio size={18} class="text-[var(--color-ink-faint)]" />
              <div>
                <p class="text-sm text-[var(--color-ink-muted)]">
                  {signal.source} {signal.signal_label || signal.signal_type}
                </p>
                <p class="text-xs text-[var(--color-ink-faint)]">{signal.detected_at?.slice(0, 16)}</p>
              </div>
            </div>
          {/each}
        </div>
      </div>
    {/if}

    {#if !data.companies?.length && !data.events?.length && !data.signals?.length}
      <p class="text-[var(--color-ink-muted)] text-center py-12">No results for "{query}"</p>
    {/if}
  {/if}
</div>
