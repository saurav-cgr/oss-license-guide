import type { AnalysisResponse, AnalyzeRequest, ApiErrorPayload } from "./types";

/** Thin, typed client for the versioned backend API. */

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
}

export interface ProviderInfoDto {
  id: string;
  models: string[];
}

export interface ProviderListResponse {
  providers: ProviderInfoDto[];
}

export interface ApiClientOptions {
  baseUrl: string;
  fetchImpl?: typeof fetch;
}

export interface AnalyzeOptions {
  /** Memory-only model-provider key sent via a request header, never persisted. */
  apiKey?: string;
  signal?: AbortSignal;
}

/** A failed API call carrying the HTTP status and a parsed stable error payload. */
export class ApiRequestError extends Error {
  readonly status: number;
  readonly payload: ApiErrorPayload | null;

  constructor(status: number, payload: ApiErrorPayload | null, message: string) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.payload = payload;
  }

  get code(): string {
    return this.payload?.error?.code ?? "unknown";
  }

  get messageText(): string {
    return this.payload?.error?.message ?? this.message;
  }
}

export class ApiClient {
  readonly baseUrl: string;
  private readonly fetchImpl?: typeof fetch;

  constructor(options: ApiClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, "");
    this.fetchImpl = options.fetchImpl;
  }

  async getHealth(): Promise<HealthResponse> {
    const doFetch = this.fetchImpl ?? globalThis.fetch;
    const response = await doFetch(`${this.baseUrl}/api/v1/health`);
    if (!response.ok) {
      throw new Error(`Health check failed with status ${response.status}`);
    }
    return (await response.json()) as HealthResponse;
  }

  /** Return the server-controlled provider allowlist and their model choices. */
  async listProviders(): Promise<ProviderListResponse> {
    const doFetch = this.fetchImpl ?? globalThis.fetch;
    const response = await doFetch(`${this.baseUrl}/api/v1/providers`);
    if (!response.ok) {
      throw new Error(`Providers request failed with status ${response.status}`);
    }
    return (await response.json()) as ProviderListResponse;
  }

  async analyze(request: AnalyzeRequest, options: AnalyzeOptions = {}): Promise<AnalysisResponse> {    const doFetch = this.fetchImpl ?? globalThis.fetch;
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (options.apiKey) {
      // The key travels only in an ephemeral request header, never in storage or URLs.
      headers["X-Model-Key"] = options.apiKey;
    }
    const response = await doFetch(`${this.baseUrl}/api/v1/analyses`, {
      method: "POST",
      headers,
      body: JSON.stringify(request),
      signal: options.signal,
    });
    if (!response.ok) {
      let payload: ApiErrorPayload | null = null;
      try {
        payload = (await response.json()) as ApiErrorPayload;
      } catch {
        // Non-JSON error body; fall back to status text below.
      }
      throw new ApiRequestError(response.status, payload, `Analysis failed with status ${response.status}`);
    }
    return (await response.json()) as AnalysisResponse;
  }
}
