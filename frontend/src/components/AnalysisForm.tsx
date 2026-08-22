import { useState } from "react";
import type { ApiClient } from "../api/client";
import type { AnalyzeRequest, FactsInput } from "../api/types";
import { ProviderSettings, type ProviderId } from "./ProviderSettings";
import { ScenarioFacts } from "./ScenarioFacts";
import type { AnalysisState } from "./useAnalysis";

interface AnalysisFormProps {
  client: ApiClient;
  state: AnalysisState;
  onRun: (request: AnalyzeRequest, apiKey?: string) => Promise<void>;
}

export function AnalysisForm({ client, state, onRun }: AnalysisFormProps) {
  const [expression, setExpression] = useState("");
  const [question, setQuestion] = useState("");
  const [facts, setFacts] = useState<FactsInput>({});
  const [provider, setProvider] = useState<ProviderId>("none");
  const [model, setModel] = useState("gemini-2.0-flash");
  const [apiKey, setApiKey] = useState("");
  const [submitError, setSubmitError] = useState<string | null>(null);

  const loading = state.status === "loading";

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = expression.trim();
    if (!trimmed) {
      setSubmitError("Enter an SPDX license expression to analyze.");
      return;
    }
    setSubmitError(null);
    const request: AnalyzeRequest = {
      expression: trimmed,
      facts,
      question: question.trim() || undefined,
      provider: provider === "none" ? undefined : provider,
      model: provider === "none" ? undefined : model,
    };
    void onRun(request, provider === "none" ? undefined : apiKey);
  }

  const banner =
    state.status === "error"
      ? state.error
      : submitError
        ? { kind: "generic" as const, message: submitError }
        : null;

  return (
    <form className="analysis-form" onSubmit={handleSubmit}>
      <div className="field">
        <label htmlFor="expression">License expression</label>
        <input
          id="expression"
          type="text"
          required
          value={expression}
          placeholder="e.g. MIT, Apache-2.0, or MIT OR Apache-2.0"
          onChange={(event) => setExpression(event.target.value)}
          disabled={loading}
        />
      </div>

      <div className="field">
        <label htmlFor="question">Your question (optional)</label>
        <textarea
          id="question"
          value={question}
          rows={2}
          placeholder="Describe your situation in your own words…"
          onChange={(event) => setQuestion(event.target.value)}
          disabled={loading}
        />
        <p className="hint">
          Context only for a model explanation; it does not change the deterministic analysis.
        </p>
      </div>

      <ProviderSettings
        client={client}
        provider={provider}
        model={model}
        apiKey={apiKey}
        onProvider={setProvider}
        onModel={setModel}
        onApiKey={setApiKey}
      />

      <ScenarioFacts value={facts} onChange={setFacts} />

      <div className="form-actions">
        <button type="submit" disabled={loading}>
          {loading ? "Analyzing…" : "Analyze"}
        </button>
      </div>

      {loading && (
        <p role="status" className="status-loading">
          Running the deterministic analysis…
        </p>
      )}

      {banner && (
        <div role="alert" className={`error-banner ${banner.kind}`}>
          {banner.message}
        </div>
      )}
    </form>
  );
}
