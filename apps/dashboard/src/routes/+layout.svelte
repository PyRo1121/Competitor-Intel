<script lang="ts">
	import favicon from '$lib/assets/favicon.svg';
	import {
		LayoutDashboard,
		Building2,
		Radio,
		Activity,
		Wallet,
		Search,
		Settings,
		Menu,
		X,
	} from 'lucide-svelte';

	let { children } = $props();
	let sidebarOpen = $state(false);

	const nav = [
		{ href: '/', label: 'Dashboard', icon: LayoutDashboard },
		{ href: '/companies', label: 'Companies', icon: Building2 },
		{ href: '/signals', label: 'Signals', icon: Radio },
		{ href: '/events', label: 'Events', icon: Activity },
		{ href: '/funding', label: 'Funding', icon: Wallet },
		{ href: '/search', label: 'Search', icon: Search },
		{ href: '/settings', label: 'Settings', icon: Settings },
	];
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<div class="min-h-screen bg-slate-50 dark:bg-slate-950">
	<header class="lg:hidden fixed top-0 inset-x-0 z-50 h-14 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex items-center px-4">
		<button onclick={() => (sidebarOpen = true)} class="p-2 -ml-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800">
			<Menu size={20} />
		</button>
		<span class="ml-3 font-semibold text-slate-900 dark:text-slate-100">Competitor Intel</span>
	</header>

	{#if sidebarOpen}
		<button class="lg:hidden fixed inset-0 z-40 bg-black/40 border-none cursor-pointer" onclick={() => (sidebarOpen = false)} aria-label="Close sidebar"></button>
	{/if}

	<aside
		class="fixed top-0 left-0 z-50 h-screen w-60 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 transition-transform duration-200 lg:translate-x-0 {sidebarOpen ? 'translate-x-0' : '-translate-x-full'}"
	>
		<div class="flex items-center justify-between h-14 px-4 border-b border-slate-200 dark:border-slate-800">
			<span class="font-semibold text-slate-900 dark:text-slate-100">Competitor Intel</span>
			<button class="lg:hidden p-2 -mr-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800" onclick={() => (sidebarOpen = false)}>
				<X size={18} />
			</button>
		</div>
		<nav class="p-3 space-y-1">
			{#each nav as item}
				<a
					href={item.href}
					class="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100 transition-colors"
				>
					<item.icon size={18} />
					{item.label}
				</a>
			{/each}
		</nav>
	</aside>

	<main class="lg:ml-60 pt-14 lg:pt-0">
		{@render children()}
	</main>
</div>
