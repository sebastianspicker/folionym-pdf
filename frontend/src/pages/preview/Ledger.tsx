import { type RefObject } from "react";
import { Breakable, Button, Checkbox, ErrorBanner, StatusPill } from "../../components";
import { PAGE_SIZE, Pagination } from "../../components/Pagination";
import { ChevronIcon, SearchIcon } from "../../icons";
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
  /** Opens the evidence for a row; used where evidence is not on screen. */
  onOpen?: (id: string) => void;
  onDismissError: () => void;
  searchRef?: RefObject<HTMLInputElement | null>;
};

type Segment = { text: string; className: string };

/** Splits a proposed name into kept and new text, with a leading date set apart. */
function proposedSegments(currentName: string, proposedName: string): Segment[] {
  const dateLength = /^\d{8}(?!\d)/.test(proposedName) ? 8 : 0;
  const segments: Segment[] = [];
  let offset = 0;
  for (const segment of changedFilenameSegments(currentName, proposedName)) {
    const base = segment.changed ? "name__new" : "name__kept";
    const end = offset + segment.text.length;
    if (offset < dateLength) {
      const split = Math.min(dateLength, end) - offset;
      segments.push({ text: segment.text.slice(0, split), className: segment.changed ? "name__date name__new" : "name__date" });
      if (split < segment.text.length) segments.push({ text: segment.text.slice(split), className: base });
    } else {
      segments.push({ text: segment.text, className: base });
    }
    offset = end;
  }
  return segments;
}

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
  onOpen,
  onDismissError,
  searchRef,
}: LedgerProps) {
  const numberWidth = Math.max(3, String(totalItems).length);
  return (
    <main className="ledger-panel" id="ledger">
      <div className="ledger-head">
        <div className="ledger-title">
          <h1>Proposed names</h1>
          <p className="lede">Tick the names to write. Nothing on disk changes until you apply.</p>
        </div>
        <div className="ledger-tools">
          <label className="search">
            <span className="visually-hidden">Search filenames</span>
            <SearchIcon />
            <input
              aria-keyshortcuts="/"
              aria-label="Search filenames"
              autoComplete="off"
              onChange={(event) => {
                onQueryChange(event.target.value);
              }}
              placeholder="Find a filename"
              ref={searchRef}
              spellCheck={false}
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
        <span className="col-no">No.</span>
        <span className="col-check" />
        <span className="col-names">Current name, then proposed name</span>
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
              aria-posinset={page * PAGE_SIZE + index + 1}
              aria-setsize={totalItems}
              className={`row ${isSelected ? "is-selected" : ""} ${isActive ? "is-active" : ""}`}
              data-id={item.id}
              data-status={item.status}
              key={item.id}
              onClick={() => {
                onActivate(item.id);
                onOpen?.(item.id);
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
                  onOpen?.(item.id);
                }
              }}
              role="option"
              tabIndex={isActive ? 0 : -1}
            >
              <span aria-hidden="true" className="row-no">
                {String(page * PAGE_SIZE + index + 1).padStart(numberWidth, "0")}
              </span>
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
                <code className="name name--from filename" title={item.current_name}>
                  <Breakable text={item.current_name} />
                </code>
                {item.proposed_name && !mutedTarget ? (
                  <code className="name name--to filename" title={item.proposed_name}>
                    <span className="visually-hidden">becomes </span>
                    {proposedSegments(item.current_name, item.proposed_name).map((segment, segmentIndex) => (
                      <span className={segment.className} key={`${segment.text}-${segmentIndex}`}>
                        <Breakable text={segment.text} />
                      </span>
                    ))}
                  </code>
                ) : (
                  <span className="name name--none">
                    {item.status === "skipped"
                      ? "Keeps its current name"
                      : item.status === "failed"
                        ? "No name proposed"
                        : "No proposal"}
                  </span>
                )}
                {item.reason && (item.status === "review" || item.status === "failed") ? (
                  <span className="row-note">{item.reason}</span>
                ) : null}
              </div>
              <StatusPill label={filterLabel(item.status)} status={item.status} />
              {onOpen ? (
                <span aria-hidden="true" className="row-open">
                  Evidence <ChevronIcon size={14} />
                </span>
              ) : null}
            </article>
          );
        })}
        {visibleItems.length === 0 && (
          <div className="table-empty">
            <strong>Nothing matches{query ? ` “${query}”` : ""}.</strong>
            <span>Clear the search or show another status.</span>
          </div>
        )}
      </div>
      <Pagination page={page} total={totalItems} onChange={onPageChange} />
    </main>
  );
}
