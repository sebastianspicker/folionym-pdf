import { useEffect, useState } from "react";
import { Breakable, StatusPill, formatBytes } from "../../components";
import { api, errorMessage, isDemo, thumbnailUrl } from "../../api";
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
      <aside className="inspector inspector--empty" aria-label="Selected document evidence">
        <p>Choose an entry to see the first page and the evidence behind its name.</p>
      </aside>
    );
  }

  const evidence = detail ?? item;
  const metadataEntries = Object.entries(detail?.metadata ?? {})
    .filter(([, value]) => value !== null && value !== "" && typeof value !== "object")
    .slice(0, 8);

  return (
    <aside className="inspector" aria-label="Selected document evidence">
      <header className="inspector-head">
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
          <figcaption className="visually-hidden">First page</figcaption>
        </figure>
        <div className="inspector-id">
          <p className="label">Evidence{isDemo ? " · demo data" : ""}</p>
          <h2 className="filename"><Breakable text={item.current_name} /></h2>
          <StatusPill status={item.status} />
        </div>
      </header>

      <section className="inspector-proposal">
        <h3 className="label">Proposed name</h3>
        {item.proposed_name ? (
          <code className="filename"><Breakable text={item.proposed_name} /></code>
        ) : (
          <p className="inspector-none">No name proposed. The file keeps its current name.</p>
        )}
      </section>

      {item.reason && (
        <section className={`inspector-note item-reason item-reason--${item.status}`}>
          <h3 className="label">Reason</h3>
          <p>{item.reason}</p>
        </section>
      )}

      {!detail && !error && (
        <p className="inspector-status" role="status">
          Reading document details…
        </p>
      )}
      {error && (
        <div className="inspector-error" role="alert">
          <p>{error}</p>
          <button className="text-button" onClick={() => setAttempt((value) => value + 1)} type="button">
            Retry evidence
          </button>
        </div>
      )}

      <dl className="evidence">
        <div>
          <dt>Size</dt>
          <dd>{formatBytes(evidence.size)}</dd>
        </div>
        <div>
          <dt>Modified</dt>
          <dd>
            {evidence.modified_at
              ? new Date(evidence.modified_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })
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
    </aside>
  );
}

export function Inspector({ item, plan }: { item: PreviewItem | null; plan: Plan }) {
  return <InspectorDetail key={`${plan.id}:${item?.id ?? "empty"}`} item={item} plan={plan} />;
}
