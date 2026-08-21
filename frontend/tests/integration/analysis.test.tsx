import { cleanup, fireEvent, render, screen } from "@testing-library/react";
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
        },
      ],
    },
  ],
  what_could_change: ["A different scenario fact could change this result."],
  evidence: [
    {
      source_id: "spdx:Apache-2.0",
      span_index: 16,
      text: "You must give any other recipients of the Work a copy of this License.",
      hash: "abc123",
    },
  ],
  confidence: { rule_coverage: "High", scenario_completeness: "High", expression_parsing: "High" },
  escalation: "No escalation required for this outcome; assumptions are disclosed.",
  disclaimer: "Informational guidance only, not legal advice.",
  missing_facts: [],
  warnings: [],
  rule_id: "apache-2.0-redistribute",
  citation_errors: [],
  blocked: false,
  rendered: "rendered fallback text",
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

function stubFetch(handlers: {
  analyses?: (init: RequestInit | undefined) => Promise<Response>;
}): FetchStub {
  return vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    if (url.endsWith("/api/v1/health")) return okJson(HEALTH);
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

    expect(await screen.findByRole("alert")).toHaveTextContent(/Analysis blocked/);
    expect(screen.getByText(/span hash mismatch/)).toBeInTheDocument();
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
});
