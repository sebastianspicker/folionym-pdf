import { Breakable } from "../../components";
import type { Plan, PreviewStatus } from "../../types";

const FILTERS: Array<{ status: PreviewStatus | "all"; label: string }> = [
  { status: "all", label: "All" },
  { status: "ready", label: "Ready" },
  { status: "review", label: "Review" },
  { status: "skipped", label: "Skipped" },
  { status: "failed", label: "Failed" },
];

export type ProcessingFact = { label: string; value: string };

type FilterRailProps = {
  plan: Plan;
  filter: PreviewStatus | "all";
  facts: ProcessingFact[];
  onFilterChange: (filter: PreviewStatus | "all") => void;
  onChangeSource: () => void;
};

function previewTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? ""
    : date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function FilterRail({ plan, filter, facts, onFilterChange, onChangeSource }: FilterRailProps) {
  const time = previewTime(plan.created_at);
  return (
    <aside className="filter-rail" aria-label="Filters and selection">
      <section className="rail-block rail-block--source">
        <h2 className="rail-title label">{plan.source_kind === "directory" ? "Folder" : "File"}</h2>
        <p className="rail-path filename" title={plan.source}>
          <Breakable text={plan.source} />
        </p>
        <p className="rail-meta">
          {plan.counts.all} {plan.counts.all === 1 ? "document" : "documents"}
          {time ? ` · previewed ${time}` : ""}
        </p>
      </section>
      <section className="rail-block rail-block--filters">
        <h2 className="rail-title label" id="filter-heading">
          Show
        </h2>
        <div className="filter-list" role="tablist" aria-labelledby="filter-heading">
          {FILTERS.map(({ status, label }) => (
            <button
              aria-selected={filter === status}
              className={`filter ${filter === status ? "is-active" : ""} ${plan.counts[status] === 0 ? "is-empty" : ""}`}
              data-status={status}
              key={status}
              onClick={() => {
                onFilterChange(status);
              }}
              role="tab"
              type="button"
            >
              <span aria-hidden="true" className={`filter-mark status--${status}`}>
                <span className="status__dot" />
              </span>
              <span className="filter-label">{label}</span>
              <span className="filter-count">{plan.counts[status]}</span>
            </button>
          ))}
        </div>
      </section>
      <section className="rail-block rail-block--facts">
        <h2 className="rail-title label">Current settings</h2>
        <dl className="fact-list">
          {facts.map((fact) => (
            <div key={fact.label}>
              <dt>{fact.label}</dt>
              <dd>{fact.value}</dd>
            </div>
          ))}
        </dl>
        <button className="text-button" onClick={onChangeSource} type="button">
          Change source or settings
        </button>
      </section>
    </aside>
  );
}
