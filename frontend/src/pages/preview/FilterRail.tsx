import { compactPath } from "../../components";
import type { Plan, PreviewStatus } from "../../types";

function filterLabel(status: PreviewStatus | "all"): string {
  switch (status) {
    case "ready":
      return "Ready";
    case "review":
      return "Review";
    case "skipped":
      return "Skipped";
    case "failed":
      return "Failed";
    default:
      return "All";
  }
}

function filterCount(plan: Plan, status: PreviewStatus | "all"): number {
  switch (status) {
    case "ready":
      return plan.counts.ready;
    case "review":
      return plan.counts.review;
    case "skipped":
      return plan.counts.skipped;
    case "failed":
      return plan.counts.failed;
    default:
      return plan.counts.all;
  }
}

const filterStatuses: Array<PreviewStatus | "all"> = [
  "all",
  "ready",
  "review",
  "skipped",
  "failed",
];

export type ProcessingFact = { label: string; value: string };

type FilterRailProps = {
  plan: Plan;
  filter: PreviewStatus | "all";
  facts: ProcessingFact[];
  onFilterChange: (filter: PreviewStatus | "all") => void;
  onChangeSource: () => void;
};

export function FilterRail({
  plan,
  filter,
  facts,
  onFilterChange,
  onChangeSource,
}: FilterRailProps) {
  return (
    <aside className="filter-rail" aria-label="Filters and selection">
      <section className="rail-block">
        <h2 className="rail-title">Scope</h2>
        <dl className="scope-list">
          <div>
            <dt>{plan.source_kind === "directory" ? "Folder" : "File"}</dt>
            <dd title={plan.source}>{compactPath(plan.source)}</dd>
          </div>
          <div>
            <dt>Documents</dt>
            <dd>{plan.counts.all}</dd>
          </div>
        </dl>
      </section>
      <section className="rail-block">
        <h2 className="rail-title" id="filter-heading">
          Status
        </h2>
        <div
          className="filter-list"
          role="tablist"
          aria-labelledby="filter-heading"
        >
          {filterStatuses.map((status) => (
            <button
              aria-selected={filter === status}
              className={`filter ${filter === status ? "is-active" : ""}`}
              key={status}
              onClick={() => {
                onFilterChange(status);
              }}
              role="tab"
              type="button"
            >
              {filterLabel(status)} <span>{filterCount(plan, status)}</span>
            </button>
          ))}
        </div>
      </section>
      <section className="rail-block rail-block--quiet">
        <h2 className="rail-title">Processing</h2>
        <ul className="fact-list">
          {facts.map((fact) => (
            <li key={fact.label}>
              <span>{fact.label}</span>
              <strong>{fact.value}</strong>
            </li>
          ))}
        </ul>
        <p className="rail-source">
          <span>Source</span>
          <strong title={plan.source}>{compactPath(plan.source)}</strong>
        </p>
        <button className="linkish" onClick={onChangeSource} type="button">
          Change source
        </button>
      </section>
    </aside>
  );
}
