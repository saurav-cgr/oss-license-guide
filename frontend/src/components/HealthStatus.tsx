import type { HealthState } from "./useHealth";

interface HealthStatusProps {
  state: HealthState;
}

export function HealthStatus({ state }: HealthStatusProps) {
  if (state.status === "loading") {
    return <p role="status">Checking backend health…</p>;
  }

  if (state.status === "error") {
    return (
      <p role="alert">
        Backend unreachable: {state.message}
      </p>
    );
  }

  return (
    <p role="status">
      Backend {state.health.status}: {state.health.service} v{state.health.version}
    </p>
  );
}
