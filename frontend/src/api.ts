import type {
  Bootstrap,
  DirectoryListing,
  Plan,
  PreviewItem,
  Report,
  Run,
  Settings,
} from "./types";
import { demoThumbnail } from "./demo/thumbnails";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : "The request could not be completed.");
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

const LOCAL_API_PREFIX = "/api/v1/";
export const isDemo = import.meta.env.MODE === "demo";

function localApiPath(path: string): string {
  // Every frontend request remains beneath the API prefix on this page's origin.
  // Return only the relative path so the browser fetch cannot target another host.
  const url = new URL(path, window.location.origin);
  if (url.origin !== window.location.origin || !url.pathname.startsWith(LOCAL_API_PREFIX)) {
    throw new Error("Folionym only permits same-origin /api/v1 requests.");
  }
  return `${url.pathname}${url.search}`;
}

function detailFromPayload(payload: unknown): unknown {
  if (typeof payload === "object" && payload !== null && "detail" in payload) {
    return payload.detail;
  }
  return payload;
}

function errorPayload(response: Response): Promise<unknown> {
  return response.json().then(detailFromPayload).catch(() => response.statusText);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await window.fetch(localApiPath(path), init);
  if (!response.ok) {
    throw new ApiError(response.status, await errorPayload(response));
  }
  return response.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

const localApi = {
  bootstrap: async () => {
    await request<{ ready: boolean }>("/api/v1/session");
    return request<Bootstrap>("/api/v1/bootstrap");
  },
  filesystem: (path: string) =>
    request<DirectoryListing>(`/api/v1/filesystem?path=${encodeURIComponent(path)}&include_counts=false`),
  startPreview: (
    sourceKind: "directory" | "file",
    path: string,
    settings: Settings,
    acknowledge = false,
  ) =>
    request<{ run_id: string }>(
      "/api/v1/previews",
      json({
        source_kind: sourceKind,
        path,
        settings,
        acknowledge_external_endpoint: acknowledge,
      }),
    ),
  run: (id: string) => request<Run>(`/api/v1/runs/${id}`),
  cancel: (id: string) => request<Run>(`/api/v1/runs/${id}/cancel`, json({})),
  plan: (id: string) => request<Plan>(`/api/v1/plans/${id}?include_metadata=false`),
  item: (id: string, itemId: string) => request<PreviewItem>(`/api/v1/plans/${id}/items/${itemId}`),
  apply: (id: string, revision: number, selectedIds: string[]) =>
    request<{ run_id: string }>(
      `/api/v1/plans/${id}/apply`,
      json({ plan_revision: revision, selected_ids: selectedIds }),
    ),
  report: (id: string) => request<Report>(`/api/v1/reports/${id}`),
};

let demoApiPromise: Promise<typeof import("./demo/api")["demoApi"]> | null =
  null;

function loadDemoApi() {
  demoApiPromise ??= import("./demo/api").then((module) => module.demoApi);
  return demoApiPromise;
}

export const api = {
  bootstrap: () =>
    isDemo ? loadDemoApi().then((client) => client.bootstrap()) : localApi.bootstrap(),
  filesystem: (path: string) =>
    isDemo
      ? loadDemoApi().then((client) => client.filesystem(path))
      : localApi.filesystem(path),
  startPreview: (
    sourceKind: "directory" | "file",
    path: string,
    settings: Settings,
    acknowledge = false,
  ) =>
    isDemo
      ? loadDemoApi().then((client) =>
          client.startPreview(sourceKind, path, settings, acknowledge),
        )
      : localApi.startPreview(sourceKind, path, settings, acknowledge),
  run: (id: string) =>
    isDemo ? loadDemoApi().then((client) => client.run(id)) : localApi.run(id),
  cancel: (id: string) =>
    isDemo
      ? loadDemoApi().then((client) => client.cancel(id))
      : localApi.cancel(id),
  plan: (id: string) =>
    isDemo ? loadDemoApi().then((client) => client.plan(id)) : localApi.plan(id),
  item: (id: string, itemId: string) =>
    isDemo ? loadDemoApi().then((client) => client.item(id, itemId)) : localApi.item(id, itemId),
  apply: (id: string, revision: number, selectedIds: string[]) =>
    isDemo
      ? loadDemoApi().then((client) =>
          client.apply(id, revision, selectedIds),
        )
      : localApi.apply(id, revision, selectedIds),
  report: (id: string) =>
    isDemo
      ? loadDemoApi().then((client) => client.report(id))
      : localApi.report(id),
};

export function thumbnailUrl(planId: string, itemId: string): string {
  if (isDemo) return demoThumbnail(itemId);
  return `/api/v1/plans/${planId}/items/${itemId}/thumbnail`;
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const detail = error.detail;
    if (typeof detail === "object" && detail !== null && "message" in detail) {
      return String(detail.message);
    }
    return error.message;
  }
  return error instanceof Error ? error.message : "Something went wrong.";
}
