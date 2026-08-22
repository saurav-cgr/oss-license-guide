import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../../src/App";

function mockHealthResponse(body: unknown, ok = true) {
  return vi.fn().mockResolvedValue({
    ok,
    status: ok ? 200 : 503,
    json: async () => body,
  } as Response);
}

describe("App health check flow", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the backend status returned by the API boundary", async () => {
    vi.stubGlobal(
      "fetch",
      mockHealthResponse({
        status: "ok",
        service: "Open Source License Information Assistant",
        version: "0.1.0",
      }),
    );

    render(<App />);

    expect(
      await screen.findByText(/Backend ok: Open Source License Information Assistant v0.1.0/),
    ).toBeInTheDocument();
  });

  it("renders an error state when the API boundary fails", async () => {
    vi.stubGlobal("fetch", mockHealthResponse({}, false));

    render(<App />);

    const alerts = await screen.findAllByRole("alert");
    expect(
      alerts.some((alert) => /Backend unreachable/.test(alert.textContent ?? "")),
    ).toBe(true);
  });
});
