import { useMemo, useState, type Dispatch, type SetStateAction } from "react";
import { PAGE_SIZE } from "../../components/Pagination";
import type { Plan, PreviewItem, PreviewStatus } from "../../types";

function isSelectable(item: PreviewItem): boolean {
  return item.status === "ready" || item.status === "review";
}

function matchesFilter(item: PreviewItem, filter: PreviewStatus | "all", normalizedQuery: string): boolean {
  if (filter !== "all" && item.status !== filter) return false;
  if (!normalizedQuery) return true;
  return (
    item.current_name.toLowerCase().includes(normalizedQuery) ||
    item.proposed_name?.toLowerCase().includes(normalizedQuery) === true
  );
}

function filterVisibleItems(plan: Plan | null, filter: PreviewStatus | "all", query: string): PreviewItem[] {
  if (!plan) return [];
  const normalizedQuery = query.trim().toLowerCase();
  return plan.items.filter((item) => matchesFilter(item, filter, normalizedQuery));
}

function toggleSelectedId(current: Set<string>, id: string): Set<string> {
  const next = new Set(current);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  return next;
}

function addSelectableItems(current: Set<string>, items: PreviewItem[]): Set<string> {
  const next = new Set(current);
  items.forEach((item) => next.add(item.id));
  return next;
}

export function usePreviewSelection(
  plan: Plan | null,
  selected: Set<string>,
  setSelected: Dispatch<SetStateAction<Set<string>>>,
  activeId: string | null,
) {
  const [filter, setFilter] = useState<PreviewStatus | "all">("all");
  const [query, setQuery] = useState("");

  const [pageState, setPageState] = useState({ page: 0, filter, query });
  const filteredItems = useMemo(() => filterVisibleItems(plan, filter, query), [filter, plan, query]);

  const page = pageState.filter === filter && pageState.query === query
    ? Math.min(pageState.page, Math.max(0, Math.ceil(filteredItems.length / PAGE_SIZE) - 1)) : 0;
  const setPage = (page: number) => setPageState({ page, filter, query });
  const visibleItems = useMemo(() => filteredItems.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE), [filteredItems, page]);
  const selectable = useMemo(() => visibleItems.filter(isSelectable), [visibleItems]);
  const activeItem = visibleItems.find((item) => item.id === activeId) ?? visibleItems[0] ?? null;
  const allVisibleSelected = selectable.length > 0 && selectable.every((item) => selected.has(item.id));

  const toggle = (id: string) => {
    setSelected((current) => toggleSelectedId(current, id));
  };

  const selectVisible = () => {
    setSelected((current) => addSelectableItems(current, selectable));
  };

  return {
    page,
    setPage,
    totalItems: filteredItems.length,
    activeId: activeItem?.id ?? null,
    activeItem,
    allVisibleSelected,
    filter,
    query,
    selectableCount: selectable.length,
    selected,
    setFilter,
    setQuery,
    setSelected,
    selectVisible,
    toggle,
    visibleItems,
  };
}
