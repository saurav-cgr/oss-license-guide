import { useEffect, useState } from "react";
import { ApiClient, type HealthResponse } from "../api/client";

export type HealthState =
  | { status: "loading" }
  | { status: "ok"; health: HealthResponse }
  | { status: "error"; message: string };

export function useHealth(client: ApiClient): HealthState {
  const [state, setState] = useState<HealthState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;

    client
      .getHealth()
      .then((health) => {
        if (!cancelled) setState({ status: "ok", health });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          const message = error instanceof Error ? error.message : "Unknown error";
          setState({ status: "error", message });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [client]);

  return state;
}
