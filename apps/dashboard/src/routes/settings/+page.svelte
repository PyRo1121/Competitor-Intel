<script lang="ts">
  import { onMount } from "svelte";
  import { getStatus, getApiBaseUrl, getAlertRules } from "$lib/api";
  import { buildIngestHealth, levelTone } from "$lib/freshness";
  import type { StatusResponse } from "$lib/types/status";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import { Activity, Database, Bell } from "lucide-svelte";

  let status = $state<StatusResponse | null>(null);
  let alertRules = $state<Record<string, unknown>[]>([]);
  let alertsError = $state<string | null>(null);

  const health = $derived(status ? buildIngestHealth(status, true) : null);
  const overallTone = $derived(health ? levelTone(health.overall) : levelTone("unknown"));

  onMount(async () => {
    try {
      status = await getStatus();
    } catch (e) {
      console.error(e);
    }
    try {
      const res = await getAlertRules();
      alertRules = res.rules ?? [];
    } catch (e) {
      alertsError = e instanceof Error ? e.message : "Failed to load alert rules";
    }
  });
</script>

<div class="ci-page max-w-3xl">
  <PageHeader title="Settings" subtitle="API connectivity, ingest catalog, and alert rules." />

  <div class="space-y-6">
    <div class="ci-panel p-6">
      <div class="flex items-center gap-3 mb-4">
        <Activity size={20} class="text-[var(--color-ink-muted)]" />
        <h2 class="text-sm font-semibold text-[var(--color-ink)]">API Status</h2>
      </div>
      {#if status}
        <div class="space-y-2">
          <div class="flex items-center gap-2">
            <div class="h-2.5 w-2.5 rounded-full bg-[var(--color-healthy)]" aria-hidden="true"></div>
            <span class="text-sm text-[var(--color-ink-muted)]">Connected</span>
            <span class="ci-mono text-xs text-[var(--color-ink-faint)]">{getApiBaseUrl()}</span>
          </div>
          {#if health}
            <p class="text-xs text-[var(--color-ink-muted)]">
              Ingest <span class="font-medium {overallTone.text}">{overallTone.label.toLowerCase()}</span>
              · {status.counts.companies} companies tracked
            </p>
          {/if}
        </div>
      {:else}
        <div class="flex items-center gap-2">
          <div class="h-2.5 w-2.5 rounded-full bg-[var(--color-stale)]"></div>
          <span class="text-sm text-[var(--color-ink-muted)]">Disconnected</span>
        </div>
      {/if}
    </div>

    <div class="ci-panel p-6">
      <div class="flex items-center gap-3 mb-4">
        <Database size={20} class="text-[var(--color-ink-muted)]" />
        <h2 class="text-sm font-semibold text-[var(--color-ink)]">Data Sources</h2>
      </div>
      {#if status?.ingestCatalog}
        <div class="space-y-2 text-sm">
          <div class="flex justify-between gap-4">
            <span class="text-[var(--color-ink-muted)]">RSS feeds (enabled)</span>
            <span class="text-[var(--color-ink)] tabular-nums">{status.ingestCatalog.rssFeedsEnabled}</span>
          </div>
          <div class="flex justify-between gap-4">
            <span class="text-[var(--color-ink-muted)]">RSS catalog (total)</span>
            <span class="text-[var(--color-ink)] tabular-nums">{status.ingestCatalog.rssFeedsTotal}</span>
          </div>
          <div class="flex justify-between gap-4">
            <span class="text-[var(--color-ink-muted)]">X monitor queries</span>
            <span class="text-[var(--color-ink)] tabular-nums">{status.ingestCatalog.xMonitorQueries}</span>
          </div>
          <div class="flex justify-between gap-4">
            <span class="text-[var(--color-ink-muted)]">YouTube channels</span>
            <span class="text-[var(--color-ink)] tabular-nums">{status.ingestCatalog.youtubeChannels}</span>
          </div>
          <p class="text-xs text-[var(--color-ink-faint)] pt-1">
            Catalog as of {status.ingestCatalog.generated}. Corpus: {status.counts.signals} signals, {status.counts.events} events.
          </p>
        </div>
      {:else if status}
        <p class="text-sm text-[var(--color-ink-muted)]">
          Ingest catalog unavailable. Corpus: {status.counts.signals} signals, {status.counts.events} events.
        </p>
      {:else}
        <p class="text-sm text-[var(--color-ink-muted)]">Connect to API to load source catalog.</p>
      {/if}
    </div>

    <div class="ci-panel p-6">
      <div class="flex items-center gap-3 mb-4">
        <Bell size={20} class="text-[var(--color-ink-muted)]" />
        <h2 class="text-sm font-semibold text-[var(--color-ink)]">Alert rules</h2>
      </div>
      {#if alertsError}
        <div class="ci-alert-error" role="alert">{alertsError}</div>
      {:else if alertRules.length === 0}
        <p class="text-sm text-[var(--color-ink-muted)]">
          No alert rules yet. Create rules via <code class="ci-mono text-xs">POST /api/alerts</code> with
          <code class="ci-mono text-xs">CI_API_KEY</code> (see docs/DEPLOY.md).
        </p>
      {:else}
        <ul class="space-y-2 text-sm">
          {#each alertRules as rule}
            <li class="flex justify-between gap-4 border-b border-[var(--color-border)] pb-2 last:border-0">
              <span class="font-medium text-[var(--color-ink)]">
                {String(rule.name ?? "Unnamed rule")}
              </span>
              <span class="text-xs text-[var(--color-ink-faint)] shrink-0">
                {String(rule.channel ?? "discord")}
              </span>
            </li>
          {/each}
        </ul>
      {/if}
    </div>
  </div>
</div>
