import { type RefObject } from "react";
import { Button, Checkbox, ErrorBanner, StatusPill } from "../../components";
import { Pagination } from "../../components/Pagination";
import { SearchIcon } from "../../icons";
import { changedFilenameSegments } from "../../lib/filenameDiff";
import type { Plan, PreviewItem, PreviewStatus } from "../../types";

function filterLabel(status: PreviewStatus): string {
  switch (status) {
    case "ready":
      return "Ready";
    case "review":
      return "Review";
    case "skipped":
      return "Skipped";
    default:
      return "Failed";
  }
}

type LedgerProps = {
  plan: Plan;
  page: number;
  totalItems: number;
  onPageChange: (page: number) => void;
  visibleItems: PreviewItem[];
  selected: Set<string>;
  activeId: string | null;
  query: string;
  error: string;
  allVisibleSelected: boolean;
  selectableCount: number;
  onQueryChange: (query: string) => void;
  onToggle: (id: string) => void;
  onSelectVisible: () => void;
  onClear: () => void;
  onActivate: (id: string) => void;
  onDismissError: () => void;
  searchRef?: RefObject<HTMLInputElement | null>;
};

export function Ledger({
  page,
  totalItems,
  onPageChange,
  visibleItems,
  selected,
  activeId,
  query,
  error,
  allVisibleSelected,
  selectableCount,
  onQueryChange,
  onToggle,
  onSelectVisible,
  onClear,
  onActivate,
  onDismissError,
  searchRef,
}: LedgerProps) {
  return (
    <section className="ledger-panel" id="ledger">
      <div className="ledger-head">
        <div>
          <p className="kicker">Preview · immutable plan once applied</p>
          <h1>Rename ledger</h1>
          <p className="lede">
            Compare source to proposed name. Checked rows keep their exact
            target on Apply.
          </p>
        </div>
        <div className="ledger-tools">
          <label className="search">
            <span className="visually-hidden">Search filenames</span>
            <SearchIcon />
            <input
              aria-label="Search filenames"
              autoComplete="off"
              onChange={(event) => {
                onQueryChange(event.target.value);
              }}
              placeholder="Filter by name…"
              ref={searchRef}
              type="search"
              value={query}
            />
            <kbd aria-hidden="true">/</kbd>
          </label>
          <div className="tool-cluster">
            <Button
              disabled={selectableCount === 0 || allVisibleSelected}
              onClick={onSelectVisible}
              type="button"
            >
              Select page
            </Button>
            <Button
              disabled={selected.size === 0}
              onClick={onClear}
              type="button"
            >
              Clear
            </Button>
          </div>
        </div>
      </div>

      {error && <ErrorBanner message={error} onDismiss={onDismissError} />}

      <div className="ledger-chrome" aria-hidden="true">
        <span className="col-check" />
        <span className="col-from">Current</span>
        <span className="col-arrow" />
        <span className="col-to">Proposed</span>
        <span className="col-status">Status</span>
      </div>

      <div
        aria-label="Proposed renames"
        aria-multiselectable="true"
        className="ledger"
        id="ledger-list"
        role="listbox"
      >
        {visibleItems.map((item, index) => {
          const isSelectable =
            item.status === "ready" || item.status === "review";
          const isSelected = selected.has(item.id);
          const isActive = activeId === item.id;
          const mutedTarget =
            !item.proposed_name ||
            item.status === "skipped" ||
            item.status === "failed";
          return (
            <article
              aria-selected={isSelected}
              aria-posinset={page * 50 + index + 1}
              aria-setsize={totalItems}
              className={`row ${isSelected ? "is-selected" : ""} ${isActive ? "is-active" : ""}`}
              data-id={item.id}
              data-status={item.status}
              key={item.id}
              onClick={() => {
                onActivate(item.id);
              }}
              onKeyDown={(event) => {
                if (event.target !== event.currentTarget) return;
                const destination = event.key === "ArrowDown" ? Math.min(index + 1, visibleItems.length - 1)
                  : event.key === "ArrowUp" ? Math.max(0, index - 1)
                  : event.key === "Home" ? 0
                  : event.key === "End" ? visibleItems.length - 1 : null;
                if (destination !== null) {
                  event.preventDefault();
                  onActivate(visibleItems[destination].id);
                  event.currentTarget.parentElement?.querySelectorAll<HTMLElement>('[role="option"]')[destination]?.focus();
                  return;
                }
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onActivate(item.id);
                }
              }}
              role="option"
              tabIndex={isActive ? 0 : -1}
            >
              <label
                className="row-check"
                onClick={(event) => {
                  event.stopPropagation();
                }}
              >
                <Checkbox
                  aria-label={`Include ${item.proposed_name ?? item.current_name}`}
                  checked={isSelected}
                  disabled={!isSelectable}
                  onChange={() => {
                    onToggle(item.id);
                  }}
                />
                <span className="visually-hidden">Include</span>
              </label>
              <div className="name-pair">
                <code className="name name--from" title={item.current_name}>
                  {item.current_name}
                </code>
                <span aria-hidden="true" className="arrow">
                  →
                </span>
                <code
                  className={`name name--to ${mutedTarget ? "name--muted" : ""}`}
                  title={item.proposed_name ?? ""}
                >
                  {item.proposed_name
                    ? changedFilenameSegments(
                        item.current_name,
                        item.proposed_name,
                      ).map((segment, index) => (
                        <span
                          className={
                            segment.changed ? "name__changed" : undefined
                          }
                          key={`${segment.text}-${index}`}
                        >
                          {segment.text}
                        </span>
                      ))
                    : item.status === "skipped"
                      ? "Unchanged · already named"
                      : item.status === "failed"
                        ? "No proposal · extract failed"
                        : "No proposal"}
                </code>
              </div>
              <StatusPill
                label={filterLabel(item.status)}
                status={item.status}
              />
            </article>
          );
        })}
        {visibleItems.length === 0 && (
          <div className="table-empty">
            <SearchIcon />
            <strong>No matching documents</strong>
            <span>Clear the search or choose another status.</span>
          </div>
        )}
      </div>
      <Pagination page={page} total={totalItems} onChange={onPageChange} />
    </section>
  );
}
