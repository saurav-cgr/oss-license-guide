import { useEffect, useState } from "react";
import type { ApiClient } from "../api/client";

export type ProviderId = "none" | "gemini" | "openai";

interface ProviderSettingsProps {
  client: ApiClient;
  provider: ProviderId;
  model: string;
  apiKey: string;
  onProvider: (provider: ProviderId) => void;
  onModel: (model: string) => void;
  onApiKey: (apiKey: string) => void;
}

interface ProviderOption {
  value: ProviderId;
  label: string;
  hint: string;
  models: string[];
}

const NONE_OPTION: ProviderOption = {
  value: "none",
  label: "Deterministic (no model)",
  hint: "No API key needed.",
  models: [],
};

/** The server allowlist fetch state. An intentionally empty allowlist is
 * distinct from a load failure or an in-flight request. */
interface ServerState {
  status: "loading" | "error" | "loaded";
  options: ProviderOption[];
}

/**
 * Provider and model selection driven by the server allowlist (GET /providers),
 * with a memory-only API-key password input. The key lives only in React
 * component state and is never written to storage, cookies, URLs, logs, or
 * analytics. Provider endpoints are server-controlled; users only bring a key.
 */
export function ProviderSettings({
  client,
  provider,
  model,
  apiKey,
  onProvider,
  onModel,
  onApiKey,
}: ProviderSettingsProps) {
  const [server, setServer] = useState<ServerState>({ status: "loading", options: [] });

  useEffect(() => {
    let cancelled = false;
    setServer({ status: "loading", options: [] });
    client
      .listProviders()
      .then((response) => {
        if (cancelled) return;
        setServer({
          status: "loaded",
          options: (response.providers ?? []).map((p) => ({
            value: p.id as ProviderId,
            label: p.id,
            hint: "Bring your own API key.",
            models: p.models,
          })),
        });
      })
      .catch(() => {
        if (!cancelled) setServer({ status: "error", options: [] });
      });
    return () => {
      cancelled = true;
    };
  }, [client]);

  // Once the server allowlist resolves, drop a selection that is not
  // allowlisted. A loaded-empty allowlist means "deterministic only", which
  // must also reset any non-none selection. Loading/error states must not
  // fall back to hard-coded providers.
  useEffect(() => {
    if (server.status !== "loaded") return;
    const ids = new Set(server.options.map((option) => option.value));
    if (provider !== "none" && !ids.has(provider)) {
      onProvider("none");
    }
  }, [server, provider, onProvider]);

  const loaded = server.status === "loaded";
  const providers = [NONE_OPTION, ...(loaded ? server.options : [])];
  const current = providers.find((option) => option.value === provider) ?? NONE_OPTION;
  const requiresKey = provider !== "none";
  const modelsForProvider = loaded
    ? (server.options.find((option) => option.value === provider)?.models ?? [])
    : [];

  return (
    <fieldset className="provider-settings">
      <legend>Model provider (optional)</legend>
      {server.status === "error" && (
        <p role="alert" className="hint provider-error">
          Could not load provider choices; deterministic analysis is available.
        </p>
      )}
      <div className="field-grid">
        <div className="field">
          <label htmlFor="provider-select">Provider</label>
          <select
            id="provider-select"
            value={provider}
            onChange={(event) => {
              const next = event.target.value as ProviderId;
              onProvider(next);
              if (next !== "none") {
                const nextModels =
                  providers.find((option) => option.value === next)?.models ?? [];
                if (nextModels.length > 0 && !nextModels.includes(model)) {
                  onModel(nextModels[0]);
                }
              }
            }}
          >
            {providers.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <p className="hint">{current.hint}</p>
        </div>
        {requiresKey && (
          <>
            <div className="field">
              <label htmlFor="model-select">Model</label>
              <select
                id="model-select"
                value={model}
                onChange={(event) => onModel(event.target.value)}
              >
                {modelsForProvider.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="api-key">API key (memory only)</label>
              <input
                id="api-key"
                type="password"
                autoComplete="off"
                value={apiKey}
                placeholder="Paste your key — cleared on refresh"
                onChange={(event) => onApiKey(event.target.value)}
              />
              <p className="hint">
                Stored only in memory for this session and cleared when the page reloads.
              </p>
            </div>
          </>
        )}
      </div>
    </fieldset>
  );
}

