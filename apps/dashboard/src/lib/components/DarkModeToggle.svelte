<script lang="ts">
  import { onMount } from "svelte";
  import { Sun, Moon } from "lucide-svelte";

  let isDark = $state(false);

  onMount(() => {
    const saved = localStorage.getItem("dark");
    isDark = saved ? saved === "true" : window.matchMedia("(prefers-color-scheme: dark)").matches;
    updateTheme();
  });

  function toggle() {
    isDark = !isDark;
    updateTheme();
  }

  function updateTheme() {
    localStorage.setItem("dark", String(isDark));
    if (isDark) document.documentElement.classList.add("dark");
    else document.documentElement.classList.remove("dark");
  }
</script>

<button
  onclick={toggle}
  class="ci-btn p-2 text-[var(--color-ink-muted)]"
  aria-label="Toggle dark mode"
>
  {#if isDark}
    <Sun size={18} />
  {:else}
    <Moon size={18} />
  {/if}
</button>
