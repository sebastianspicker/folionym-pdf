import { useCallback, useRef, useState } from "react";
import { api, errorMessage } from "../../api";
import { useRun } from "../../hooks/useRun";
import { navigate } from "../../lib/routing";
import type { Plan, Run } from "../../types";

type UsePreviewApplyOptions = {
  plan: Plan | null;
  selected: Set<string>;
};

export function usePreviewApply({ plan, selected }: UsePreviewApplyOptions) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [applying, setApplying] = useState(false);
  // A ref, not state: a second click can arrive before the re-render that disables the button.
  const applyingRef = useRef(false);
  const [applyError, setApplyError] = useState("");
  const onRunComplete = useCallback((run: Run) => {
    if ((run.state === "completed" || run.state === "cancelled") && run.report_id) {
      sessionStorage.setItem("folionym.report", run.report_id);
      navigate("apply");
    }
  }, []);
  const { run, error: runError, setError: setRunError, retry: retryRun } = useRun(runId, onRunComplete);

  const apply = async () => {
    if (!plan || applyingRef.current) return;
    applyingRef.current = true;
    setApplying(true);
    try {
      const result = await api.apply(plan.id, [...selected]);
      setConfirmOpen(false);
      setRunId(result.run_id);
    } catch (requestError: unknown) {
      setApplyError(errorMessage(requestError));
      setConfirmOpen(false);
    } finally {
      applyingRef.current = false;
      setApplying(false);
    }
  };

  const cancelRun = () => {
    if (runId) void api.cancel(runId);
  };

  const closeRun = () => {
    setRunId(null);
    setRunError("");
  };

  return {
    apply,
    applying,
    applyError,
    clearApplyError: () => setApplyError(""),
    cancelRun,
    closeConfirm: () => setConfirmOpen(false),
    closeRun,
    confirmOpen,
    openConfirm: () => setConfirmOpen(true),
    run,
    runError,
    retryRun,
  };
}
