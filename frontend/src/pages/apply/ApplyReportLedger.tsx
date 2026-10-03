import { useMemo, useState } from "react";
import { Pagination, PAGE_SIZE } from "../../components/Pagination";
import { StatusPill } from "../../components";
import { ArrowRightIcon, DocumentIcon } from "../../icons";
import type { ApplyItem, ApplyStatus } from "../../types";

const reportFilters: Array<ApplyStatus | "all"> = ["all", "renamed", "skipped", "unchanged", "failed", "cancelled"];

export function ApplyReportLedger({ items }: { items: ApplyItem[] }) {
  const [filter, setFilter] = useState<ApplyStatus | "all">("all");
  const [requestedPage, setPage] = useState(0);
  const filteredItems = useMemo(() => items.filter((item) => filter === "all" || item.status === filter), [items, filter]);
  const page = Math.min(requestedPage, Math.max(0, Math.ceil(filteredItems.length / PAGE_SIZE) - 1));
  const visibleItems = filteredItems.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  return (
    <section className="result-list">
      <header>
        <div>
          <span className="eyebrow">Ledger</span>
          <h2>Per-file outcome</h2>
        </div>
        <div className="result-filters">
          {reportFilters.map((status) => (
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
              {status}
            </button>
          ))}
        </div>
      </header>
      <div className="result-table">
        {visibleItems.map((item) => (
          <div className="result-row" key={item.item_id}>
            <DocumentIcon />
            <span>{item.source_name}</span>
            <ArrowRightIcon />
            <strong>{item.target_name ?? "No target"}</strong>
            <StatusPill status={item.status === "skipped" ? "unchanged" : item.status} />
            {item.reason && <small>{item.reason}</small>}
          </div>
        ))}
      </div>
      {visibleItems.length === 0 && <p role="status">No matching outcomes.</p>}
      <Pagination page={page} total={filteredItems.length} onChange={setPage} />
    </section>
  );
}
