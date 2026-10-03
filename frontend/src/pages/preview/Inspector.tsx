import { useEffect, useState } from "react";
import { StatusPill, formatBytes } from "../../components";
import { api, errorMessage, isDemo, thumbnailUrl } from "../../api";
import { DocumentIcon } from "../../icons";
import type { Plan, PreviewItem } from "../../types";

function InspectorDetail({
  item,
  plan,
}: {
  item: PreviewItem | null;
  plan: Plan;
}) {
  const [detail, setDetail] = useState<PreviewItem | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [thumbnail, setThumbnail] = useState<"loading" | "ready" | "error">("loading");
  useEffect(() => {
    if (!item) return;
    let active = true;
    setError("");
    void api.item(plan.id, item.id).then((next) => {
      if (active) setDetail(next);
    }).catch((error: unknown) => { if (active) setError(errorMessage(error)); });
    return () => { active = false; };
  }, [plan.id, item?.id, attempt]);
  if (!item) {
    return (
      <aside
        className="inspector inspector--empty"
        aria-label="Selected document evidence"
      >
        <DocumentIcon size={28} />
        <p>Select a document to inspect its naming evidence.</p>
      </aside>
    );
  }

  const evidence = detail ?? item;
  const metadataEntries = Object.entries(detail?.metadata ?? {})
    .filter(
      ([, value]) =>
        value !== null && value !== "" && typeof value !== "object",
    )
    .slice(0, 8);

  return (
    <aside className="inspector" aria-label="Selected document evidence">
      <div className="inspector-head">
        <p className="kicker">Evidence</p>
        {isDemo && <p className="kicker">Demo data · no files are changed</p>}
        <h2>{item.current_name}</h2>
        <StatusPill status={item.status} />
      </div>
      {!detail && !error && <p role="status">Loading document evidence…</p>}
      {error && <div role="alert"><p>{error}</p><button onClick={() => setAttempt((value) => value + 1)}>Retry evidence</button></div>}
      <figure className="thumb">
        <div className="thumb-frame">
          {thumbnail === "loading" && <span role="status">Loading first page…</span>}
          {thumbnail === "error" && <span role="status">First page unavailable.</span>}
          <img
            hidden={thumbnail !== "ready"}
            onLoad={() => setThumbnail("ready")}
            onError={() => setThumbnail("error")}
            alt={`First page of ${item.current_name}`}
            src={thumbnailUrl(plan.id, item.id)}
          />
        </div>
        <figcaption>First page</figcaption>
      </figure>
      <dl className="evidence">
        <div>
          <dt>Proposed</dt>
          <dd>
            <code>{item.proposed_name ?? "No proposal"}</code>
          </dd>
        </div>
        <div>
          <dt>Size</dt>
          <dd>{formatBytes(evidence.size)}</dd>
        </div>
        <div>
          <dt>Modified</dt>
          <dd>
            {evidence.modified_at
              ? new Date(evidence.modified_at).toLocaleString()
              : "Unavailable"}
          </dd>
        </div>
        {metadataEntries.map(([key, value]) => (
          <div key={key}>
            <dt>{key.replaceAll("_", " ")}</dt>
            <dd>{String(value)}</dd>
          </div>
        ))}
      </dl>
      {item.reason && (
        <div
          className={`inspector-note item-reason item-reason--${item.status}`}
        >
          <strong>Why this name</strong>
          <p>{item.reason}</p>
        </div>
      )}
    </aside>
  );
}

export function Inspector({ item, plan }: { item: PreviewItem | null; plan: Plan }) {
  return <InspectorDetail key={`${plan.id}:${item?.id ?? "empty"}`} item={item} plan={plan} />;
}
