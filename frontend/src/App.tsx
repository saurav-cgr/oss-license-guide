import { ApiClient } from "./api/client";
import { HealthStatus } from "./components/HealthStatus";
import { useHealth } from "./components/useHealth";

const apiClient = new ApiClient({ baseUrl: import.meta.env.VITE_API_BASE_URL ?? "" });

export function App() {
  const health = useHealth(apiClient);

  return (
    <main>
      <h1>Open Source License Information Assistant</h1>
      <p>Milestone 0 scaffold — frontend-to-API connectivity check.</p>
      <HealthStatus state={health} />
    </main>
  );
}
