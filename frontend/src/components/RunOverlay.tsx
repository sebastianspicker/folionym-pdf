import type { CSSProperties } from "react";
import { terminalStates } from "../hooks/useRun";
import type { Run } from "../types";
import { Button } from "./Button";
import { ErrorBanner } from "./ErrorBanner";
import { Modal } from "./Modal";

export function RunOverlay({
  run,
  error,
  onCancel,
  onClose,
  onRetry,
}: {
  run: Run | null;
  error: string;
  onCancel: () => void;
  onClose: () => void;
  onRetry: () => void;
}) {
  const isTerminal = run ? terminalStates.has(run.state) : false;
  const percentage = run?.total ? Math.round((run.completed / run.total) * 100) : 0;
  return (
    <Modal
      description={
        run?.kind === "apply"
          ? "Writing only the exact names you ticked."
          : "Reading each PDF on this computer and proposing a name. Nothing is renamed."
      }
      onClose={isTerminal || error ? onClose : () => undefined}
      open={Boolean(run) || Boolean(error)}
      title={run?.kind === "apply" ? "Writing names" : "Building preview"}
    >
      {error ? (
        <><ErrorBanner message={error} /><Button onClick={onRetry}>Retry connection</Button></>
      ) : (
        <div className="run-status">
          <div className="run-status__row">
            <strong>{run?.message || "Starting…"}</strong>
            <span className="run-count">
              {run?.total ? (
                <>
                  {run.completed}
                  <small> / {run.total}</small>
                </>
              ) : null}
            </span>
          </div>
          <div
            aria-label={`${percentage}% complete`}
            aria-valuemax={100}
            aria-valuemin={0}
            aria-valuenow={percentage}
            className={run?.total ? "progress" : "progress progress--indeterminate"}
            role="progressbar"
          >
            <span style={{ "--progress": percentage / 100 } as CSSProperties} />
          </div>
          <p className="run-file filename">{run?.current_file || "Preparing…"}</p>
          {run?.error && <ErrorBanner message={run.error} />}
          {!isTerminal && (
            <Button onClick={onCancel} variant="secondary">
              Stop after this file
            </Button>
          )}
        </div>
      )}
    </Modal>
  );
}
