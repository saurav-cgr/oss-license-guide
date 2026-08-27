import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../../src/App";
import type { AnalysisResponse } from "../../src/api/types";

const HEALTH = {
  status: "ok",
  service: "Open Source License Information Assistant",
  version: "0.1.0",
};

const SAMPLE: AnalysisResponse = {
  outcome: "Permitted with listed obligations",
  canonical: "Apache-2.0",
  short_answer: "Apache-2.0 is permitted provided the listed obligations are satisfied.",
  assumptions: ["action = redistribute", "distribution = True"],
  obligations: [
    {
      text: "Retain the license and attribution notices.",
      citations: [
        {
          source_id: "spdx:Apache-2.0",
          span_index: 16,
          text: "You must give any other recipients of the Work a copy of this License.",
          hash: "abc123",
          source_type: "spdx",
          source_url: "https://spdx.org/licenses/Apache-2.0.html",
          version: "3.24.0",
          retrieved_at: "2026-08-21T14:47:43Z",
        },
      ],
    },
  ],
  permission: {
    text: "Permission to use Apache-2.0 under the stated scenario",
    citations: [
      {
        source_id: "spdx:Apache-2.0@3.24.0",
        span_index: 13,
        text: "Subject to the terms and conditions of this License, each Contributor hereby grants to You a perpetual, worldwide, non-exclusive, no-charge, royalty-free, irrevocable copyright license.",
        hash: "def456",
        source_type: "spdx",
        source_url: "https://spdx.org/licenses/Apache-2.0.html",
        version: "3.24.0",
        retrieved_at: "2026-08-21T14:47:43Z",
      },
    ],
  },
  what_could_change: ["A different scenario fact could change this result."],
  evidence: [
    {
      source_id: "spdx:Apache-2.0",
      span_index: 16,
      text: "You must give any other recipients of the Work a copy of this License.",
      hash: "abc123",
      source_type: "spdx",
      source_url: "https://spdx.org/licenses/Apache-2.0.html",
      version: "3.24.0",
      retrieved_at: "2026-08-21T14:47:43Z",
    },
  ],
  confidence: { rule_coverage: "High", scenario_completeness: "High", expression_parsing: "High" },
  escalation: "No escalation required for this outcome; assumptions are disclosed.",
  disclaimer: "Informational guidance only, not legal advice.",
  missing_facts: [],
  warnings: [],
  rule_id: "apache-2.0-redistribute",
  rule: {
    rule_id: "apache-2.0-redistribute",
    review_status: "maintainer_reviewed",
    reviewer: "maintainer",
    effective_date: "2026-08-21",
    last_verified_at: "2026-08-21",
    rule_version: "1",
    content_hash: "0123456789abcdef",
  },
  citation_errors: [],
  blocked: false,
  rendered: "rendered fallback text",
  explanation: "",
  provider: null,
  model: null,
  provider_note: "",
};

function okJson(body: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response);
}

function errorJson(status: number, code: string, message: string) {
  return Promise.resolve({
    ok: false,
    status,
    json: async () => ({ error: { code, message } }),
  } as Response);
}

type FetchStub = ReturnType<typeof vi.fn>;

const PROVIDERS = {
  providers: [
    { id: "gemini", models: ["gemini-3.5-flash-lite"] },
    { id: "openai", models: ["gpt-4o-mini"] },
  ],
};

function stubFetch(handlers: {
  analyses?: (init: RequestInit | undefined) => Promise<Response>;
  providers?: () => Promise<Response>;
}): FetchStub {
  return vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    if (url.endsWith("/api/v1/health")) return okJson(HEALTH);
    if (url.endsWith("/api/v1/providers")) {
      if (handlers.providers) return handlers.providers();
      return okJson(PROVIDERS);
    }
    if (url.endsWith("/api/v1/analyses")) {
      if (handlers.analyses) return handlers.analyses(init);
      return okJson(SAMPLE);
    }
    return okJson({});
  });
}

function submitAnalysis(expression = "Apache-2.0") {
  fireEvent.change(screen.getByLabelText(/License expression/), {
    target: { value: expression },
  });
  fireEvent.click(screen.getByRole("button", { name: /Analyze/ }));
}

describe("analysis experience", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it("renders the structured deterministic result after a successful analysis", async () => {
    vi.stubGlobal("fetch", stubFetch({}));
    render(<App />);

    submitAnalysis();

    expect(await screen.findByText("Permitted with listed obligations")).toBeInTheDocument();
    expect(
      screen.getByText(/Apache-2.0 is permitted provided the listed obligations are satisfied/),
    ).toBeInTheDocument();
    expect(screen.getByText("Retain the license and attribution notices.")).toBeInTheDocument();
    expect(screen.getAllByText(/spdx:Apache-2.0/).length).toBeGreaterThan(0);
    expect(
      screen.getAllByText("You must give any other recipients of the Work a copy of this License.")
        .length,
    ).toBeGreaterThan(0);
    expect(screen.getAllByText("High").length).toBeGreaterThan(0);
    expect(screen.getByText(/Informational guidance only, not legal advice/)).toBeInTheDocument();
  });

  it("shows a loading state while the request is in flight", async () => {
    let resolveAnalysis!: (value: Response) => void;
    const pending = new Promise<Response>((resolve) => {
      resolveAnalysis = resolve;
    });
    vi.stubGlobal("fetch", stubFetch({ analyses: () => pending }));
    render(<App />);

    submitAnalysis();
    expect(await screen.findByText(/Analyzing/)).toBeInTheDocument();

    resolveAnalysis(await okJson(SAMPLE));
    expect(await screen.findByText("Permitted with listed obligations")).toBeInTheDocument();
  });

  it("renders a generic error state when the API boundary fails", async () => {
    vi.stubGlobal(
      "fetch",
      stubFetch({ analyses: () => Promise.reject(new Error("network down")) }),
    );
    render(<App />);

    submitAnalysis();

    expect(await screen.findByRole("alert")).toHaveTextContent(/network down/);
  });

  it("renders an invalid-key state for a 401 response", async () => {
    vi.stubGlobal(
      "fetch",
      stubFetch({
        analyses: () => errorJson(401, "invalid_provider_key", "The API key is invalid."),
      }),
    );
    render(<App />);

    submitAnalysis();

    expect(await screen.findByRole("alert")).toHaveTextContent(/API key is invalid/);
  });

  it("renders a timeout state for an aborted request", async () => {
    vi.stubGlobal(
      "fetch",
      stubFetch({
        analyses: () =>
          Promise.reject(new DOMException("The operation was aborted.", "AbortError")),
      }),
    );
    render(<App />);

    submitAnalysis();

    expect(await screen.findByRole("alert")).toHaveTextContent(/timed out/);
  });

  it("renders an abstention state for a blocked answer", async () => {
    const blocked: AnalysisResponse = {
      ...SAMPLE,
      outcome: "Insufficient information",
      short_answer: "Insufficient information to reach a conclusion; provide the missing facts.",
      blocked: true,
      citation_errors: ["span hash mismatch for spdx:Apache-2.0@16"],
      obligations: [],
      evidence: [],
    };
    vi.stubGlobal("fetch", stubFetch({ analyses: () => okJson(blocked) }));
    render(<App />);

    submitAnalysis();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/supporting evidence could not be validated/);
    expect(screen.getByText(/span hash mismatch/)).toBeInTheDocument();
    // No substantive conclusion is shown when the answer is blocked.
    expect(screen.queryByText(/permitted provided the listed obligations/)).not.toBeInTheDocument();
    expect(screen.queryByText("Retain the license and attribution notices.")).not.toBeInTheDocument();
  });

  it("surfaces a timeout when the real timer aborts the request", async () => {
    vi.useFakeTimers();
    const fetchStub = stubFetch({
      analyses: (init) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () =>
            reject(new DOMException("aborted", "AbortError")),
          );
        }),
    });
    vi.stubGlobal("fetch", fetchStub);
    render(<App />);

    submitAnalysis();
    // Advance past the 15s timeout so the real setTimeout -> abort path fires.
    await vi.advanceTimersByTimeAsync(15001);

    expect(screen.getByRole("alert")).toHaveTextContent(/timed out/);
    vi.useRealTimers();
  });

  it("renders only server-allowlisted providers", async () => {
    const fetchStub = vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.endsWith("/api/v1/health")) return okJson(HEALTH);
      if (url.endsWith("/api/v1/providers"))
        return okJson({ providers: [{ id: "gemini", models: ["gemini-3.5-flash-lite"] }] });
      if (url.endsWith("/api/v1/analyses")) return okJson(SAMPLE);
      return okJson({});
    });
    vi.stubGlobal("fetch", fetchStub);
    render(<App />);

    const select = await screen.findByLabelText(/Provider/);
    await waitFor(() => {
      const options = Array.from(select.querySelectorAll("option")).map((o) => o.textContent);
      expect(options).toContain("Deterministic (no model)");
      expect(options).toContain("gemini");
      // "openai" is not in the server allowlist and must not be selectable.
      expect(options).not.toContain("openai");
    });
  });

  it("renders a missing-facts prompt when the outcome depends on unknown facts", async () => {
    const incomplete: AnalysisResponse = {
      ...SAMPLE,
      outcome: "Insufficient information",
      short_answer: "Insufficient information to reach a conclusion; provide the missing facts.",
      missing_facts: ["action", "distribution"],
      obligations: [],
      evidence: [],
    };
    vi.stubGlobal("fetch", stubFetch({ analyses: () => okJson(incomplete) }));
    render(<App />);

    submitAnalysis();

    expect(await screen.findByRole("alert")).toHaveTextContent(/Missing information/);
    expect(screen.getByText("action")).toBeInTheDocument();
    expect(screen.getByText("distribution")).toBeInTheDocument();
  });

  it("keeps the API key out of storage and sends it only in a request header", async () => {
    let capturedInit: RequestInit | undefined;
    const fetchStub = stubFetch({
      analyses: (init) => {
        capturedInit = init;
        return okJson(SAMPLE);
      },
    });
    vi.stubGlobal("fetch", fetchStub);
    render(<App />);

    await waitFor(() => {
      const select = screen.getByLabelText(/Provider/) as HTMLSelectElement;
      expect([...select.options].some((option) => option.value === "gemini")).toBe(true);
    });
    fireEvent.change(screen.getByLabelText(/Provider/), { target: { value: "gemini" } });
    fireEvent.change(await screen.findByLabelText(/API key/), {
      target: { value: "sk-secret-123" },
    });
    submitAnalysis();

    await screen.findByText("Permitted with listed obligations");

    const headers = (capturedInit?.headers ?? {}) as Record<string, string>;
    expect(headers["X-Model-Key"]).toBe("sk-secret-123");
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
  });

  it("renders a model explanation and provider note when present", async () => {
    const withExplanation: AnalysisResponse = {
      ...SAMPLE,
      explanation: "The license permits use with attribution.",
      provider: "gemini",
      model: "gemini-3.5-flash-lite",
      provider_note: "Model explanation unavailable; deterministic result shown.",
    };
    vi.stubGlobal("fetch", stubFetch({ analyses: () => okJson(withExplanation) }));
    render(<App />);

    submitAnalysis();

    expect(await screen.findByText("Model explanation")).toBeInTheDocument();
    expect(screen.getByText("The license permits use with attribution.")).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/deterministic result shown/);
  });

  it("shows the deterministic fallback result even when a model provider is selected", async () => {
    const fetchStub = stubFetch({
      analyses: (init) => {
        const headers = (init?.headers ?? {}) as Record<string, string>;
        // Provider key present, but the deterministic answer is still returned and shown.
        expect(headers["X-Model-Key"]).toBe("sk-provider-key");
        return okJson(SAMPLE);
      },
    });
    vi.stubGlobal("fetch", fetchStub);
    render(<App />);

    await waitFor(() => {
      const select = screen.getByLabelText(/Provider/) as HTMLSelectElement;
      expect([...select.options].some((option) => option.value === "gemini")).toBe(true);
    });
    fireEvent.change(screen.getByLabelText(/Provider/), { target: { value: "gemini" } });
    fireEvent.change(await screen.findByLabelText(/API key/), {
      target: { value: "sk-provider-key" },
    });
    submitAnalysis();

    expect(await screen.findByText("Permitted with listed obligations")).toBeInTheDocument();
    expect(
      screen.getByText(/Apache-2.0 is permitted provided the listed obligations are satisfied/),
    ).toBeInTheDocument();
  });

  it("renders the cited permission claim, rule provenance, and source metadata", async () => {
    vi.stubGlobal("fetch", stubFetch({}));
    render(<App />);

    submitAnalysis();

    expect(await screen.findByText("Permissions")).toBeInTheDocument();
    expect(screen.getByText(/Permission to use Apache-2.0/)).toBeInTheDocument();
    expect(screen.getByText("Rule provenance")).toBeInTheDocument();
    expect(screen.getByText("maintainer_reviewed")).toBeInTheDocument();
    expect(screen.getAllByText(/spdx · v3\.24\.0/).length).toBeGreaterThan(0);
  });

  it("shows deterministic-only when the server allowlist is intentionally empty", async () => {
    vi.stubGlobal(
      "fetch",
      stubFetch({ providers: () => okJson({ providers: [] }) }),
    );
    render(<App />);

    await waitFor(() => {
      const select = screen.getByLabelText(/Provider/) as HTMLSelectElement;
      expect([...select.options].map((option) => option.value)).toEqual(["none"]);
    });
  });

  it("surfaces an error note when the provider allowlist fails to load", async () => {
    vi.stubGlobal(
      "fetch",
      stubFetch({ providers: () => errorJson(500, "server_error", "boom") }),
    );
    render(<App />);

    expect(await screen.findByRole("alert")).toHaveTextContent(/Could not load provider choices/);
    const select = screen.getByLabelText(/Provider/) as HTMLSelectElement;
    expect([...select.options].map((option) => option.value)).toEqual(["none"]);
  });
});
