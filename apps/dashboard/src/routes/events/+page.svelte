<script lang="ts">
  import { onMount } from "svelte";
  import { getEvents, type IntelligenceEventRecord } from "$lib/api";
  import SearchBar from "$lib/components/SearchBar.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import { formatUsd } from "$lib/format";
  import { TrendingUp, AlertCircle, Zap, ExternalLink } from "lucide-svelte";

  let events = $state<IntelligenceEventRecord[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  onMount(async () => {
    try {
      const res = await getEvents({ limit: 100 });
      events = res.events || [];
    } catch (e) {
      error = e instanceof Error ? e.message : "Failed to load events";
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
    if (type?.includes("funding")) return "text-[var(--color-healthy)]";
    if (type?.includes("acquisition")) return "text-[var(--color-warning)]";
    if (type?.includes("launch")) return "text-[var(--color-accent-bright)]";
    return "text-[var(--color-ink-faint)]";
  }

  function companyHref(event: IntelligenceEventRecord): string | null {
    if (event.company_slug) return `/companies/${event.company_slug}`;
    if (event.company_id != null) return `/companies/${event.company_id}`;
    return null;
  }
</script>

<div class="ci-page">
  <PageHeader title="Events" subtitle="Intelligence events">
    {#snippet actions()}
      <SearchBar />
    {/snippet}
  </PageHeader>

  {#if error}
    <div class="ci-alert-error mb-6" role="alert">{error}</div>
  {:else if loading}
    <div class="space-y-3">
      {#each [1, 2, 3, 4, 5] as _}
        <div class="ci-skeleton h-20"></div>
      {/each}
    </div>
  {:else}
    <div class="space-y-3">
      {#each events as event}
        {@const Icon = eventIcon(event.event_type)}
        {@const href = companyHref(event)}
        <div class="ci-panel p-5">
          <div class="flex items-start gap-4">
            <div class="mt-0.5 {eventColor(event.event_type)}">
              <Icon size={18} />
            </div>
            <div class="flex-1 min-w-0">
              <div class="flex flex-wrap items-center gap-2 mb-1">
                {#if href}
                  <a href={href} class="ci-link font-medium">
                    {event.company_name || "Unknown"}
                  </a>
                {:else}
                  <span class="font-medium text-[var(--color-ink)]">
                    {event.company_name || "Unknown"}
                  </span>
                {/if}
                <span class="text-[var(--color-ink-faint)]">—</span>
                <span class="text-sm text-[var(--color-ink-muted)]">{event.event_type}</span>
              </div>
              {#if event.amount_usd}
                <p class="text-sm font-medium text-[var(--color-healthy)]">
                  {formatUsd(event.amount_usd)}
                </p>
              {/if}
              {#if event.source_url}
                <a
                  href={event.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  class="mt-2 inline-flex items-center gap-1 text-xs text-[var(--color-ink-muted)] hover:text-[var(--color-accent)]"
                >
                  <ExternalLink size={12} />
                  Source
                </a>
              {/if}
            </div>
            <span class="ci-mono text-xs text-[var(--color-ink-faint)] whitespace-nowrap">
              {event.created_at?.slice(0, 16).replace("T", " ") || "—"}
            </span>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
