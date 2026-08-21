/** Thin, typed client for the versioned backend API. */

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
}

export interface ApiClientOptions {
  baseUrl: string;
  fetchImpl?: typeof fetch;
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
}
