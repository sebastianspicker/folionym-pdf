import { useMemo, useState } from "react";
import { Pagination, PAGE_SIZE } from "../../components/Pagination";
import { Breakable, StatusPill } from "../../components";
import type { ApplyItem, ApplyStatus } from "../../types";

const reportFilters: Array<{ status: ApplyStatus | "all"; label: string }> = [
  { status: "all", label: "All" },
  { status: "renamed", label: "Renamed" },
  { status: "failed", label: "Failed" },
  { status: "unchanged", label: "Unchanged" },
  { status: "skipped", label: "Skipped" },
  { status: "cancelled", label: "Cancelled" },
];

function statusLabel(status: ApplyStatus): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

export function ApplyReportLedger({ items }: { items: ApplyItem[] }) {
  const [filter, setFilter] = useState<ApplyStatus | "all">("all");
  const [requestedPage, setPage] = useState(0);
  const counts = useMemo(() => {
    const result: Record<ApplyStatus | "all", number> = {
      all: items.length, renamed: 0, skipped: 0, unchanged: 0, failed: 0, cancelled: 0,
    };
    for (const item of items) result[item.status] += 1;
    return result;
  }, [items]);
  const filteredItems = useMemo(() => items.filter((item) => filter === "all" || item.status === filter), [items, filter]);
  const page = Math.min(requestedPage, Math.max(0, Math.ceil(filteredItems.length / PAGE_SIZE) - 1));
  const visibleItems = filteredItems.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const numberWidth = Math.max(3, String(items.length).length);
  const entryNumbers = useMemo(() => new Map(items.map((item, index) => [item.item_id, index + 1])), [items]);

  return (
    <section aria-labelledby="report-title" className="result-list">
      <header className="result-list__head">
        <h2 id="report-title">All files</h2>
        <div aria-label="Show outcomes" className="result-filters" role="group">
          {reportFilters
            .filter(({ status }) => status === "all" || status === filter || counts[status] > 0)
            .map(({ status, label }) => (
              <button
                aria-pressed={filter === status}
                className={filter === status ? "is-active" : ""}
                key={status}
                onClick={() => {
                  setFilter(status);
                  setPage(0);
                }}
                type="button"
              >
                {label} <span>{counts[status]}</span>
              </button>
            ))}
        </div>
      </header>
      <div className="result-table">
        {visibleItems.map((item) => (
          <div className="result-row" data-status={item.status} key={item.item_id}>
            <span aria-hidden="true" className="row-no">
              {String(entryNumbers.get(item.item_id) ?? 0).padStart(numberWidth, "0")}
            </span>
            <div className="name-pair">
              <code className="name name--from filename"><Breakable text={item.source_name} /></code>
              {item.target_name ? (
                <code className="name name--to filename">
                  <span className="visually-hidden">{item.status === "renamed" ? "renamed to " : "proposed "}</span>
                  {/* A written name carries the marker: this is what changed on disk. */}
                  <span className={item.status === "renamed" ? "highlight" : undefined}>
                    <Breakable text={item.target_name} />
                  </span>
                </code>
              ) : (
                <span className="name name--none">No new name</span>
              )}
              {item.reason && <small className="row-note">{item.reason}</small>}
            </div>
            <StatusPill label={statusLabel(item.status)} status={item.status} />
          </div>
        ))}
      </div>
      {visibleItems.length === 0 && <p className="table-empty" role="status">No outcomes of this kind.</p>}
      <Pagination page={page} total={filteredItems.length} onChange={setPage} />
    </section>
  );
}
