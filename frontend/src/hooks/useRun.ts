import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorMessage, isDemo } from "../api";
import type { Run } from "../types";

export const terminalStates = new Set(["completed", "cancelled", "failed"]);
const events = ["run.snapshot", "run.started", "run.progress", "run.cancelling", "run.completed", "run.cancelled", "run.failed"];
const MAX_FAILURES = 5;

export function useRun(runId: string | null, onComplete: (run: Run) => void) {
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const completeRef = useRef(onComplete);
  completeRef.current = onComplete;
  const retry = useCallback(() => setAttempt((value) => value + 1), []);
  useEffect(() => {
    setRun(null);
    setError("");
    if (!runId) return;
    let active = true;
    let finished = false;
    let failures = 0;
    let timeout = 0;
    let stream: EventSource | null = null;
    let generation = 0;
    const accept = (next: Run) => {
      if (!active || finished || next.id !== runId) return;
      failures = 0;
      setError("");
      setRun(next);
      if (terminalStates.has(next.state)) {
        finished = true;
        window.clearTimeout(timeout);
        stream?.close();
        completeRef.current(next);
      }
    };
    const poll = async () => {
      const requestGeneration = generation;
      try {
        const next = await api.run(runId);
        if (!active || finished) return;
        if (generation === requestGeneration) accept(next);
        if (!finished) timeout = window.setTimeout(poll, stream ? 5000 : 350);
      } catch (requestError: unknown) {
        if (!active || finished) return;
        if (generation !== requestGeneration) {
          timeout = window.setTimeout(poll, stream ? 5000 : 350);
          return;
        }
        failures += 1;
        setError(`${errorMessage(requestError)} ${failures < MAX_FAILURES ? "Reconnecting…" : "Automatic retries paused. Retry to check this run."}`);
        if (failures < MAX_FAILURES) timeout = window.setTimeout(poll, Math.min(8000, 500 * 2 ** (failures - 1)));
        else { stream?.close(); stream = null; }
      }
    };
    if (!isDemo && typeof EventSource !== "undefined") {
      try {
        stream = new EventSource(`/api/v1/runs/${encodeURIComponent(runId)}/events`);
        const receive = (event: MessageEvent<string>) => {
          try {
            const next = JSON.parse(event.data) as Run;
            if (next.id !== runId || typeof next.state !== "string") return;
            generation += 1;
            accept(next);
          } catch { /* A malformed event leaves the polling safety net active. */ }
        };
        events.forEach((name) => stream?.addEventListener(name, receive as EventListener));
        stream.onerror = () => {
          stream?.close();
          stream = null;
          // The existing single poll loop resumes at its next bounded interval.
        };
      } catch { stream = null; }
    }
    void poll();
    return () => {
      active = false;
      window.clearTimeout(timeout);
      stream?.close();
    };
  }, [runId, attempt]);
  return { run, error, setError, retry };
}
