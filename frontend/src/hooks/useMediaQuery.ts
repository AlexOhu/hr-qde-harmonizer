import { useSyncExternalStore } from "react";

/**
 * Abonniert eine CSS-Media-Query.
 *
 * `useSyncExternalStore` statt `useEffect` + State: die Komponente rendert
 * beim ersten Durchlauf schon mit dem richtigen Wert, statt kurz mit dem
 * falschen Layout aufzublitzen.
 */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onStoreChange) => {
      if (typeof window === "undefined" || !window.matchMedia) return () => {};
      const list = window.matchMedia(query);
      list.addEventListener("change", onStoreChange);
      return () => list.removeEventListener("change", onStoreChange);
    },
    () =>
      typeof window !== "undefined" && window.matchMedia
        ? window.matchMedia(query).matches
        : false,
    () => false,
  );
}

/** Ab dieser Breite steht das Detail dauerhaft neben der Liste. */
export function useIsWideViewport(): boolean {
  return useMediaQuery("(min-width: 1024px)");
}
