import { ApiClient } from "./api/client";
import { AnalysisForm } from "./components/AnalysisForm";
import { AnalysisResult } from "./components/AnalysisResult";
import { HealthStatus } from "./components/HealthStatus";
import { useAnalysis } from "./components/useAnalysis";
import { useHealth } from "./components/useHealth";

const apiClient = new ApiClient({ baseUrl: import.meta.env.VITE_API_BASE_URL ?? "" });

export function App() {
  const health = useHealth(apiClient);
  const analysis = useAnalysis(apiClient);

  return (
    <main>
      <h1>Open Source License Information Assistant</h1>
      <p className="tagline">
        Deterministic, source-backed guidance about likely software-license obligations.
        Informational only, not legal advice.
      </p>
      <HealthStatus state={health} />
      <AnalysisForm client={apiClient} state={analysis.state} onRun={analysis.run} />
      {analysis.state.status === "success" && <AnalysisResult result={analysis.state.result} />}
    </main>
  );
}

