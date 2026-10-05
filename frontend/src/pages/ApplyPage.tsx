import { useEffect, useState } from "react";
import { api, errorMessage, isDemo } from "../api";
import { AppChrome, Button, PageLoader } from "../components";
import { ArrowRightIcon, WarningIcon } from "../icons";
import { isLocalEndpoint } from "../lib/privacy";
import { navigate } from "../lib/routing";
import type { Bootstrap, Report } from "../types";
import { ApplyReportLedger } from "./apply/ApplyReportLedger";

const TALLY: Array<{ key: keyof Report["counts"]; label: string }> = [
  { key: "renamed", label: "Renamed" },
  { key: "failed", label: "Failed" },
  { key: "unchanged", label: "Unchanged" },
  { key: "skipped", label: "Skipped" },
  { key: "cancelled", label: "Cancelled" },
];

function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

function headline(counts: Report["counts"]): { title: string; detail: string } {
  const problems = counts.failed + counts.cancelled;
  if (problems > 0) {
    const parts = [`${counts.renamed} renamed`, counts.failed ? `${counts.failed} failed` : "", counts.cancelled ? `${counts.cancelled} cancelled` : ""];
    return {
      title: parts.filter(Boolean).join(", "),
      detail:
        "Failed and unreached files were not changed. Each one lists the reason.",
    };
  }
  if (counts.renamed === 0) {
    return { title: "Nothing was renamed", detail: "No file on disk changed. Each line below says why." };
  }
  return {
    title: `${plural(counts.renamed, "file")} renamed`,
    detail: "Each file passed its fingerprint and collision checks, then received the exact name you reviewed.",
  };
}

export function ApplyPage({ bootstrap }: { bootstrap: Bootstrap }) {
  const reportId = sessionStorage.getItem("folionym.report");
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!reportId) {
      navigate("source");
      return;
    }
    const loadReport = async () => {
      try {
        setReport(await api.report(reportId));
      } catch (requestError: unknown) {
        setError(errorMessage(requestError));
      }
    };
    void loadReport();
  }, [reportId]);

  if (!report && !error) return <PageLoader label="Loading report" />;
  if (!report) {
    return (
      <div className="fatal-state">
        <WarningIcon />
        <h1>This report is gone</h1>
        <p>{error}</p>
        <Button onClick={() => {
          navigate("source");
        }}>Back to Source</Button>
      </div>
    );
  }

  const localOnly = isLocalEndpoint(bootstrap.settings);
  const summary = headline(report.counts);

  return (
    <AppChrome
      active={3}
      external={!localOnly}
      source={report.source}
      sourceMeta={`${report.items.length} items`}
    >
      <main className="result-shell">
        <header className="result-heading">
          <div>
            <h1>{summary.title}</h1>
            <p>{summary.detail}</p>
            {isDemo ? (
              <p className="result-demo-note">Demo report. No file on your computer was changed.</p>
            ) : null}
          </div>
          <Button onClick={() => {
            navigate("source");
          }} type="button" variant="primary">
            New source <ArrowRightIcon />
          </Button>
        </header>
        {TALLY.some(({ key }) => report.counts[key] > 0) ? (
          <section aria-label="Apply totals">
            {/* Only outcomes that happened are counted; a row of zeros says nothing. */}
            <dl className="tally">
              {TALLY.filter(({ key }) => report.counts[key] > 0).map(({ key, label }) => (
                <div className={`tally-cell tally-cell--${key}`} key={key}>
                  <dt>{label}</dt>
                  <dd>{report.counts[key]}</dd>
                </div>
              ))}
            </dl>
          </section>
        ) : null}
        <ApplyReportLedger items={report.items} />
        <p className="result-footnote">
          This report lasts only while Folionym runs. For an undo trail, set a rename log under Fine-tune → Output,
          then use <code>folionym-undo</code> from a terminal.
        </p>
      </main>
    </AppChrome>
  );
}
