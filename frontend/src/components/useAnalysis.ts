import { useCallback, useRef, useState } from "react";
import { ApiClient, ApiRequestError } from "../api/client";
import type { AnalysisResponse, AnalyzeRequest } from "../api/types";

const REQUEST_TIMEOUT_MS = 15000;

export type AnalysisState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; result: AnalysisResponse }
  | { status: "error"; error: { kind: "invalid-key" | "timeout" | "generic"; message: string } };

function classify(error: unknown): { kind: "invalid-key" | "timeout" | "generic"; message: string } {
  if (error instanceof ApiRequestError) {
    if (error.status === 401 || error.status === 403) {
      return { kind: "invalid-key", message: error.messageText };
    }
    return { kind: "generic", message: error.messageText };
  }
  if (error instanceof DOMException && error.name === "AbortError") {
    return { kind: "timeout", message: "The request timed out. Please try again." };
  }
  const message = error instanceof Error ? error.message : "Unknown error";
  return { kind: "generic", message };
}

export interface UseAnalysis {
  state: AnalysisState;
  run: (request: AnalyzeRequest, apiKey?: string) => Promise<void>;
  reset: () => void;
}

/** Runs a single analysis request with a bounded timeout and cancellable controller. */
export function useAnalysis(client: ApiClient): UseAnalysis {
  const [state, setState] = useState<AnalysisState>({ status: "idle" });
  const controllerRef = useRef<AbortController | null>(null);

  const reset = useCallback(() => {
    controllerRef.current?.abort();
    controllerRef.current = null;
    setState({ status: "idle" });
  }, []);

  const run = useCallback(
    async (request: AnalyzeRequest, apiKey?: string) => {
      controllerRef.current?.abort();
      const controller = new AbortController();
      controllerRef.current = controller;

      setState({ status: "loading" });
      const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
      try {
        const result = await client.analyze(request, { apiKey, signal: controller.signal });
        if (!controller.signal.aborted) {
          setState({ status: "success", result });
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          setState({ status: "error", error: classify(error) });
        }
      } finally {
        clearTimeout(timeoutId);
      }
    },
    [client],
  );

  return { state, run, reset };
}
