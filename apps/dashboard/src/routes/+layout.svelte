<script lang="ts">
	import "../app.css";
	import { onDestroy, onMount } from "svelte";
	import { page } from "$app/stores";
	import { QueryClientProvider } from "@tanstack/svelte-query";
	import { getAppQueryClient } from "$lib/queryClient";
	import favicon from "$lib/assets/favicon.svg";
	import { ApiError, getStatus } from "$lib/api";
	import FreshnessBanner from "$lib/components/FreshnessBanner.svelte";
	import type { StatusResponse } from "$lib/types/status";
	import {
		LayoutDashboard,
		Building2,
		Radio,
		Activity,
		Wallet,
		Briefcase,
		Search,
		ScanSearch,
		Settings,
		Shield,
		Menu,
		X,
	} from "lucide-svelte";

	const STATUS_POLL_MS = 60_000;

	let { children } = $props();
	const queryClient = getAppQueryClient();
	let sidebarOpen = $state(false);
	let status = $state<StatusResponse | null>(null);
	let statusLoading = $state(true);
	let apiReachable = $state(true);
	let pollTimer: ReturnType<typeof setInterval> | undefined;

	const nav = [
		{ href: "/", label: "Dashboard", icon: LayoutDashboard, exact: true },
		{ href: "/companies", label: "Companies", icon: Building2 },
		{ href: "/discovery", label: "Discovery", icon: ScanSearch },
		{ href: "/signals", label: "Signals", icon: Radio },
		{ href: "/events", label: "Events", icon: Activity },
		{ href: "/funding", label: "Funding", icon: Wallet },
		{ href: "/jobs", label: "Jobs", icon: Briefcase },
		{ href: "/search", label: "Search", icon: Search },
		{ href: "/data-quality", label: "Data quality", icon: Shield },
		{ href: "/settings", label: "Settings", icon: Settings },
	];

	function isActive(href: string, exact = false): boolean {
		const path = $page.url.pathname;
		if (exact) return path === href;
		return path === href || (href !== "/" && path.startsWith(href + "/"));
	}

	async function refreshStatus() {
		statusLoading = true;
		try {
			status = await getStatus();
			apiReachable = true;
		} catch (err) {
			apiReachable = !(err instanceof ApiError);
			if (err instanceof ApiError && err.status >= 500) {
				apiReachable = false;
			}
			console.error("Failed to load ingest status", err);
		} finally {
			statusLoading = false;
		}
	}

	onMount(() => {
		void refreshStatus();
		pollTimer = setInterval(() => void refreshStatus(), STATUS_POLL_MS);
	});

	onDestroy(() => {
		if (pollTimer) clearInterval(pollTimer);
	});
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>Competitor Intel</title>
</svelte:head>

<div class="min-h-screen">
	<header
		class="lg:hidden fixed top-0 inset-x-0 z-50 h-14 border-b border-[var(--color-border)] bg-[var(--color-canvas-elevated)]/95 backdrop-blur-md flex items-center px-4"
	>
		<button
			type="button"
			onclick={() => (sidebarOpen = true)}
			class="p-2 -ml-2 rounded-lg text-[var(--color-ink-muted)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-ink)]"
			aria-label="Open navigation"
		>
			<Menu size={20} />
		</button>
		<span class="ml-3 ci-display text-lg font-medium text-[var(--color-ink)]">Competitor Intel</span>
	</header>

	{#if sidebarOpen}
		<button
			type="button"
			class="lg:hidden fixed inset-0 z-40 bg-black/60 border-none cursor-pointer backdrop-blur-sm"
			onclick={() => (sidebarOpen = false)}
			aria-label="Close sidebar"
		></button>
	{/if}

	<aside
		class="fixed top-0 left-0 z-50 flex h-screen w-[15.5rem] flex-col border-r border-[var(--color-border)] bg-[var(--color-canvas-elevated)] transition-transform duration-200 lg:translate-x-0 {sidebarOpen
			? 'translate-x-0'
			: '-translate-x-full'}"
		aria-label="Main navigation"
	>
		<div class="flex h-[4.25rem] items-center gap-3 border-b border-[var(--color-border-subtle)] px-5">
			<div
				class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-[var(--color-accent)]/40 bg-[var(--color-accent-muted)] ci-mono text-xs font-semibold text-[var(--color-accent-bright)]"
				aria-hidden="true"
			>
				CI
			</div>
			<div class="min-w-0 flex-1">
				<p class="ci-display truncate text-base font-medium leading-tight text-[var(--color-ink)]">
					Competitor Intel
				</p>
				<p class="truncate text-[0.65rem] uppercase tracking-widest text-[var(--color-ink-faint)]">
					Briefing room
				</p>
			</div>
			<button
				type="button"
				class="lg:hidden p-2 rounded-lg text-[var(--color-ink-muted)] hover:bg-[var(--color-surface-hover)]"
				onclick={() => (sidebarOpen = false)}
				aria-label="Close navigation"
			>
				<X size={18} />
			</button>
		</div>

		<nav class="flex-1 overflow-y-auto p-3 space-y-0.5">
			{#each nav as item}
				{@const active = isActive(item.href, item.exact)}
				<a
					href={item.href}
					onclick={() => (sidebarOpen = false)}
					class="group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors {active
						? 'bg-[var(--color-accent-muted)] text-[var(--color-ink)]'
						: 'text-[var(--color-ink-muted)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-ink)]'}"
					aria-current={active ? "page" : undefined}
				>
					{#if active}
						<span
							class="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-[var(--color-accent)]"
							aria-hidden="true"
						></span>
					{/if}
					<item.icon
						size={18}
						class={active ? "text-[var(--color-accent-bright)]" : "opacity-70"}
						aria-hidden="true"
					/>
					{item.label}
				</a>
			{/each}
		</nav>

		<div class="border-t border-[var(--color-border-subtle)] p-4">
			<p class="text-[0.65rem] leading-relaxed text-[var(--color-ink-faint)]">
				Signals, funding, and hiring — one operational view.
			</p>
		</div>
	</aside>

	<div class="lg:ml-[15.5rem] pt-14 lg:pt-0 flex flex-col min-h-screen">
		<FreshnessBanner
			{status}
			{apiReachable}
			loading={statusLoading}
			onRefresh={refreshStatus}
		/>
		<main class="flex-1">
			<QueryClientProvider client={queryClient}>
				{@render children()}
			</QueryClientProvider>
		</main>
	</div>
</div>
