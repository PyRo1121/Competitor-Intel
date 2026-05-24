import { QueryClient } from "@tanstack/svelte-query";

function buildQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        gcTime: 5 * 60_000,
        refetchOnWindowFocus: false,
        retry: 1,
      },
    },
  });
}

let appQueryClient: QueryClient | undefined;

/** Singleton — one client per browser session. */
export function getAppQueryClient(): QueryClient {
  appQueryClient ??= buildQueryClient();
  return appQueryClient;
}
