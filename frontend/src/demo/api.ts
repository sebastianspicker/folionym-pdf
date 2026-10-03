import type { Plan, Report, Run, Settings } from "../types";
import { clonePlan, cloneReport, demoBootstrap, demoListing, demoPlan } from "./fixtures";

type DemoRun = {
  kind: Run["kind"];
  planId: string | null;
  reportId: string | null;
  pollCount: number;
  cancelled: boolean;
};

let activePlan = clonePlan(demoPlan);
let latestReport: Report | null = null;
const runs = new Map<string, DemoRun>();

function cloneBootstrap() {
  return {
    ...demoBootstrap,
    settings: { ...demoBootstrap.settings },
    roots: demoBootstrap.roots.map((root) => ({ ...root })),
    capabilities: { ...demoBootstrap.capabilities },
  };
}

function runSnapshot(id: string, demoRun: DemoRun): Run {
  const total =
    demoRun.kind === "preview"
      ? activePlan.items.length
      : latestReport?.items.length ?? 0;
  const completed = demoRun.cancelled
    ? 0
    : Math.min(
        total,
        demoRun.pollCount * Math.max(1, Math.ceil(total / 2)),
      );
  const state = demoRun.cancelled
    ? "cancelled"
    : demoRun.pollCount === 0
      ? "queued"
      : demoRun.pollCount < 2
        ? "running"
        : "completed";
  demoRun.pollCount += 1;
  return {
    id,
    kind: demoRun.kind,
    state,
    completed: state === "completed" ? total : completed,
    total,
    current_file:
      state === "completed"
        ? "Demo complete"
        : activePlan.items[Math.min(completed, activePlan.items.length - 1)]
            ?.current_name ?? "Preparing demo",
    message:
      state === "queued"
        ? "Preparing deterministic demo data"
        : state === "completed"
          ? "Demo complete"
          : "Processing demo documents",
    plan_id:
      state === "completed" && demoRun.kind === "preview"
        ? demoRun.planId
        : null,
    report_id:
      state === "completed" && demoRun.kind === "apply"
        ? demoRun.reportId
        : null,
    error: null,
  };
}

function buildReport(selectedIds: string[]): Report {
  const selected = new Set(selectedIds);
  const items = activePlan.items.map((item) => {
    const rename =
      selected.has(item.id) &&
      (item.status === "ready" || item.status === "review");
    if (rename) {
      if (item.id === "demo-hetzner") {
        return {
          item_id: item.id,
          source_name: item.current_name,
          target_name: item.proposed_name,
          status: "failed" as const,
          reason:
            "Source changed after Preview; fingerprint mismatch. No file was renamed.",
        };
      }
      return {
        item_id: item.id,
        source_name: item.current_name,
        target_name: item.proposed_name,
        status: "renamed" as const,
        reason: "Demo result. No local file was changed.",
      };
    }
    if (item.status === "failed") {
      return {
        item_id: item.id,
        source_name: item.current_name,
        target_name: null,
        status: "failed" as const,
        reason: item.reason,
      };
    }
    return {
      item_id: item.id,
      source_name: item.current_name,
      target_name: item.proposed_name,
      status: "unchanged" as const,
      reason: item.status === "skipped" ? item.reason : "Not selected in this demo run.",
    };
  });
  return {
    id: "demo-report",
    plan_id: activePlan.id,
    source: activePlan.source,
    started_at: "2024-05-02T10:02:00Z",
    completed_at: "2024-05-02T10:02:02Z",
    items,
    counts: {
      renamed: items.filter((item) => item.status === "renamed").length,
      skipped: 0,
      unchanged: items.filter((item) => item.status === "unchanged").length,
      failed: items.filter((item) => item.status === "failed").length,
      cancelled: 0,
    },
  };
}

latestReport = buildReport(
  activePlan.items.filter((item) => item.included).map((item) => item.id),
);

export const demoApi = {
  bootstrap: async () => cloneBootstrap(),
  filesystem: async (path: string) => {
    const listing = demoListing(path);
    return {
      ...listing,
      entries: listing.entries.map((entry) => ({ ...entry, pdf_count: null })),
    };
  },
  startPreview: async (
    sourceKind: "directory" | "file",
    path: string,
    _settings: Settings,
    _acknowledgedEndpoint = "",
  ) => {
    const templateItems =
      sourceKind === "file" ? demoPlan.items.slice(0, 1) : demoPlan.items;
    const items = templateItems.map((item) => ({
      ...item,
      source_path:
        sourceKind === "file" ? path : `${path || demoPlan.source}/${item.current_name}`,
      metadata: { ...item.metadata },
    }));
    activePlan = {
      ...clonePlan(demoPlan),
      source: path || demoPlan.source,
      source_kind: sourceKind,
      items,
      counts: {
        all: items.length,
        ready: items.filter((item) => item.status === "ready").length,
        review: items.filter((item) => item.status === "review").length,
        skipped: items.filter((item) => item.status === "skipped").length,
        failed: items.filter((item) => item.status === "failed").length,
      },
    };
    const runId = "demo-preview-run";
    runs.set(runId, {
      kind: "preview",
      planId: activePlan.id,
      reportId: null,
      pollCount: 0,
      cancelled: false,
    });
    return { run_id: runId };
  },
  run: async (id: string) => {
    const demoRun = runs.get(id);
    if (!demoRun) throw new Error("The deterministic demo run is unavailable.");
    return runSnapshot(id, demoRun);
  },
  cancel: async (id: string) => {
    const demoRun = runs.get(id);
    if (!demoRun) throw new Error("The deterministic demo run is unavailable.");
    demoRun.cancelled = true;
    return runSnapshot(id, demoRun);
  },
  plan: async (_id: string): Promise<Plan> => ({ ...clonePlan(activePlan), items: activePlan.items.map((item) => ({ ...item, metadata: {} })) }),
  item: async (_id: string, itemId: string) => {
    const item = activePlan.items.find((item) => item.id === itemId);
    if (!item) throw new Error("Document unavailable.");
    return { ...item, metadata: { ...item.metadata } };
  },
  apply: async (_id: string, _revision: number, selectedIds: string[]) => {
    latestReport = buildReport(selectedIds);
    const runId = "demo-apply-run";
    runs.set(runId, {
      kind: "apply",
      planId: null,
      reportId: latestReport.id,
      pollCount: 0,
      cancelled: false,
    });
    return { run_id: runId };
  },
  report: async (_id: string): Promise<Report> => {
    if (!latestReport) throw new Error("The deterministic demo report is unavailable.");
    return cloneReport(latestReport);
  },
};
