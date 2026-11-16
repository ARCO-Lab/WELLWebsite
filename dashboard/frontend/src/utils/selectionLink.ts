// The query-string side of hooks/useSelectionLink: reading and writing ?tab=, ?groups= and ?creeks=. Pure functions,
// tested in scripts/selectionLink.test.mjs.

import { searchString } from "./searchString.ts";

/** The known names in a comma-separated parameter, in their usual order. */
export function namesFromParam<K extends string>(value: string | null, known: readonly K[]): K[] {
  const asked = new Set((value ?? "").split(",").map((s) => s.trim()));
  return known.filter((k) => asked.has(k));
}

/** A query string with this selection written in (empty values removed), other parameters kept. */
export function searchWithSelection(search: string, tab: "sensor" | "sampling", groups: string[], creeks: string[]): string {
  const q = new URLSearchParams(search);
  const put = (name: string, value: string) => (value ? q.set(name, value) : q.delete(name));
  put("tab", tab === "sampling" ? "sampling" : "");
  put("groups", groups.join(","));
  put("creeks", creeks.join(","));
  return searchString(q);
}
