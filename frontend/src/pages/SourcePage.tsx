import { useCallback, useState } from "react";
import { ApiError, api, errorMessage, isDemo } from "../api";
import {
  AppChrome,
  Breakable,
  Button,
  ErrorBanner,
  Field,
  FineTuneDrawer,
  FolderBrowser,
  Modal,
  NameAnatomy,
  RunOverlay,
  TextInput,
} from "../components";
import { useRun } from "../hooks/useRun";
import { ArrowRightIcon, FolderIcon, SlidersIcon, WarningIcon } from "../icons";
import { isLocalEndpoint } from "../lib/privacy";
import { navigate } from "../lib/routing";
import type { Bootstrap, Run, Settings } from "../types";

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rule-row">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function caseLabel(value: Settings["case"]): string {
  if (value === "snakeCase") return "snake_case";
  if (value === "camelCase") return "camelCase";
  return "kebab-case";
}

type ExternalEndpointAcknowledgementDetail = {
  code: "external_endpoint_ack_required";
  endpoint: unknown;
};

function isConflictApiError(error: unknown): error is ApiError {
  return error instanceof ApiError && error.status === 409;
}

function isExternalEndpointAcknowledgementDetail(
  detail: unknown,
): detail is ExternalEndpointAcknowledgementDetail {
  if (detail === null || typeof detail !== "object") return false;
  if (!("code" in detail) || !("endpoint" in detail)) return false;
  return detail.code === "external_endpoint_ack_required";
}

function requiresExternalEndpointAcknowledgement(
  error: unknown,
): error is ApiError & { detail: ExternalEndpointAcknowledgementDetail } {
  return isConflictApiError(error) && isExternalEndpointAcknowledgementDetail(error.detail);
}

export function SourcePage({
  bootstrap,
  onBootstrapChange,
}: {
  bootstrap: Bootstrap;
  onBootstrapChange: (bootstrap: Bootstrap) => void;
}) {
  const [settings, setSettings] = useState(bootstrap.settings);
  const [kind, setKind] = useState<"directory" | "file">(bootstrap.settings.single_file ? "file" : "directory");
  const [path, setPath] = useState(bootstrap.settings.single_file || bootstrap.settings.directory);
  const [folderOpen, setFolderOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [startError, setStartError] = useState("");
  const [ack, setAck] = useState<{ endpoint: string } | null>(null);

  const updateSetting = (key: keyof Settings, value: Settings[keyof Settings]) => {
    setSettings((current) => ({ ...current, [key]: value }));
  };

  const onRunComplete = useCallback((run: Run) => {
    if (run.state === "completed" && run.plan_id) {
      sessionStorage.setItem("folionym.plan", run.plan_id);
      sessionStorage.removeItem("folionym.report");
      navigate("preview");
    }
  }, []);

  const { run, error: runError, setError: setRunError, retry: retryRun } = useRun(runId, onRunComplete);

  const startPreview = async (acknowledgedEndpoint = "") => {
    setStartError("");
    if (!path.trim()) {
      setStartError(`Choose a ${kind === "file" ? "PDF" : "folder"} before continuing.`);
      return;
    }
    try {
      const result = await api.startPreview(kind, path.trim(), settings, acknowledgedEndpoint);
      setAck(null);
      setRunId(result.run_id);
      onBootstrapChange({ ...bootstrap, settings });
    } catch (requestError: unknown) {
      if (requiresExternalEndpointAcknowledgement(requestError)) {
        setAck({ endpoint: String(requestError.detail.endpoint ?? settings.llm_url) });
        return;
      }
      setStartError(errorMessage(requestError));
    }
  };

  const localOnly = isLocalEndpoint(settings);

  return (
    <AppChrome
      active={1}
      external={!localOnly}
      overlays={
        <>
          <FolderBrowser
            bootstrap={bootstrap}
            initialPath={path || settings.directory}
            onChoose={(chosen) => {
              setPath(chosen);
              setSettings((current) => ({ ...current, directory: chosen }));
              setFolderOpen(false);
            }}
            onClose={() => {
              setFolderOpen(false);
            }}
            open={folderOpen}
          />
          <FineTuneDrawer
            onChange={updateSetting}
            onClose={() => {
              setDrawerOpen(false);
            }}
            open={drawerOpen}
            settings={settings}
          />
          <Modal
            footer={
              <>
                <Button onClick={() => {
                  setAck(null);
                }}>Cancel</Button>
                <Button onClick={() => {
                  void startPreview(ack?.endpoint ?? "");
                }} variant="primary">
                  Send and build preview
                </Button>
              </>
            }
            onClose={() => {
              setAck(null);
            }}
            open={Boolean(ack)}
            title="Send document text off this computer?"
          >
            <div className="consent">
              <WarningIcon />
              <div>
                <p>Preview will send text extracted from these PDFs to a model outside this computer:</p>
                <code className="consent-endpoint filename"><Breakable text={ack?.endpoint ?? ""} /></code>
                <p>This confirmation covers only this exact endpoint, for this session.</p>
              </div>
            </div>
          </Modal>
          <RunOverlay
            error={runError}
            onRetry={retryRun}
            onCancel={() => {
              if (runId) void api.cancel(runId);
            }}
            onClose={() => {
              setRunId(null);
              setRunError("");
            }}
            run={run}
          />
        </>
      }
      source={path}
    >
      <main className="source-shell">
        <header className="source-heading">
          <h1>Choose the PDFs to rename</h1>
          <p>Folionym reads each PDF and proposes a name from its contents. Nothing is renamed until you apply.</p>
        </header>

        <section aria-labelledby="source-slip-title" className="source-slip">
          <h2 className="visually-hidden" id="source-slip-title">Source</h2>
          <div aria-label="Source type" className="segmented" role="group">
            <button
              aria-pressed={kind === "directory"}
              className={kind === "directory" ? "is-active" : ""}
              onClick={() => {
                setKind("directory");
                setPath(settings.directory);
              }}
              type="button"
            >
              Folder
            </button>
            <button
              aria-pressed={kind === "file"}
              className={kind === "file" ? "is-active" : ""}
              onClick={() => {
                setKind("file");
                setPath(settings.single_file);
              }}
              type="button"
            >
              Single PDF
            </button>
          </div>
          {startError && <ErrorBanner message={startError} onDismiss={() => {
            setStartError("");
          }} />}
          {kind === "directory" ? (
            <div className="source-picker">
              <FolderIcon className="source-picker__icon" size={24} />
              <div className="source-picker__copy">
                {path ? (
                  <code className="source-path filename"><Breakable text={path} /></code>
                ) : (
                  <span className="source-path source-path--empty">No folder chosen yet</span>
                )}
                <span>
                  {settings.recursive
                    ? "PDFs in this folder and its subfolders."
                    : "PDFs directly in this folder. Subfolders are left out."}
                </span>
              </div>
              <Button onClick={() => {
                setFolderOpen(true);
              }} type="button">
                {path ? "Change folder" : "Choose folder"}
              </Button>
            </div>
          ) : (
            <Field className="source-file-field" hint="The full path to one PDF on this computer." label="PDF path">
              <TextInput
                onChange={(event) => {
                  setPath(event.target.value);
                }}
                placeholder="/Users/you/Documents/scan.pdf"
                spellCheck={false}
                value={path}
              />
            </Field>
          )}
          {isDemo ? (
            <p className="source-demo-note">
              This demo folder holds simulated documents. Nothing on your computer is read.
            </p>
          ) : null}
          <div className="source-go">
            <Button className="source-start" onClick={() => {
              void startPreview();
            }} type="button" variant="primary">
              Build preview <ArrowRightIcon />
            </Button>
          </div>
        </section>

        <aside aria-labelledby="source-next-title" className="source-aside">
          <h2 id="source-next-title">What happens next</h2>
          <ul className="assurances">
            <li>
              <strong>Preview</strong> Reads each PDF and proposes a name. No file is changed.
            </li>
            <li>
              <strong>Review</strong> Tick the names you want. Uncertain names are marked Review, with the reason.
            </li>
            <li>
              <strong>Apply</strong> Renames only the ticked files, after checking each file and target again.
            </li>
          </ul>
        </aside>

        <section aria-labelledby="rules-title" className="rules">
          <header className="rules-head">
            <h2 id="rules-title">Naming rules</h2>
            <Button onClick={() => {
              setDrawerOpen(true);
            }} type="button">
              <SlidersIcon /> Fine-tune
            </Button>
          </header>
          <NameAnatomy settings={settings} />
          <dl className="rule-list">
            <SummaryRow label="Case" value={caseLabel(settings.case)} />
            <SummaryRow label="Document language" value={settings.language === "de" ? "German" : "English"} />
            <SummaryRow
              label="Ambiguous dates"
              value={settings.date_format === "dmy" ? "Read as day / month / year" : "Read as month / day / year"}
            />
            <SummaryRow label="Text" value={settings.use_ocr ? "Text layer, OCR for scans" : "Text layer only"} />
            <SummaryRow
              label="Model"
              value={
                settings.use_llm
                  ? `${settings.llm_model || "Configured model"}, ${localOnly ? "loopback endpoint" : "external endpoint"}`
                  : "None. Rules and heuristics only"
              }
            />
          </dl>
        </section>
      </main>
    </AppChrome>
  );
}
