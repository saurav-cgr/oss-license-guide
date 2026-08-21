export type ProviderId = "none" | "gemini" | "openai";

interface ProviderSettingsProps {
  provider: ProviderId;
  model: string;
  apiKey: string;
  onProvider: (provider: ProviderId) => void;
  onModel: (model: string) => void;
  onApiKey: (apiKey: string) => void;
}

const PROVIDERS: { value: ProviderId; label: string; hint: string }[] = [
  { value: "none", label: "Deterministic (no model)", hint: "No API key needed." },
  { value: "gemini", label: "Gemini", hint: "Explain structured findings." },
  { value: "openai", label: "OpenAI-compatible", hint: "Bring your own endpoint." },
];

const MODELS: Record<Exclude<ProviderId, "none">, string[]> = {
  gemini: ["gemini-2.0-flash"],
  openai: ["gpt-4o-mini"],
};

/**
 * Provider and model selection with a memory-only API-key password input.
 * The key lives only in React component state and is never written to
 * storage, cookies, URLs, logs, or analytics.
 */
export function ProviderSettings({
  provider,
  model,
  apiKey,
  onProvider,
  onModel,
  onApiKey,
}: ProviderSettingsProps) {
  const requiresKey = provider !== "none";

  return (
    <fieldset className="provider-settings">
      <legend>Model provider (optional)</legend>
      <div className="field-grid">
        <div className="field">
          <label htmlFor="provider-select">Provider</label>
          <select
            id="provider-select"
            value={provider}
            onChange={(event) => {
              const next = event.target.value as ProviderId;
              onProvider(next);
              if (next !== "none" && !MODELS[next].includes(model)) {
                onModel(MODELS[next][0]);
              }
            }}
          >
            {PROVIDERS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
          <p className="hint">
            {PROVIDERS.find((p) => p.value === provider)?.hint ?? ""}
          </p>
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
                {MODELS[provider].map((m) => (
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
