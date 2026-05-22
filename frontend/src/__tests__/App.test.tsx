import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import App from "../App";

function mockFetch(data: unknown, ok = true) {
  vi.spyOn(globalThis, "fetch").mockResolvedValue({
    ok,
    json: () => Promise.resolve(data),
  } as Response);
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("App", () => {
  it("renders the app title", () => {
    mockFetch({
      status: "ok",
      gcp_project: "test-project",
      bq_reachable: true,
      lineage_api_reachable: true,
    });
    render(<App />);
    expect(screen.getAllByText("Catalog Agent").length).toBeGreaterThan(0);
  });

  it("shows Connected badge when bq_reachable is true", async () => {
    mockFetch({
      status: "ok",
      gcp_project: "test-project",
      bq_reachable: true,
      lineage_api_reachable: true,
    });
    render(<App />);
    await waitFor(() => expect(screen.getByText("Connected")).toBeInTheDocument());
  });

  it("shows Unavailable badge when bq_reachable is false", async () => {
    mockFetch({
      status: "ok",
      gcp_project: "test-project",
      bq_reachable: false,
      lineage_api_reachable: false,
    });
    render(<App />);
    await waitFor(() => expect(screen.getByText("Unavailable")).toBeInTheDocument());
  });

  it("shows Unavailable badge on fetch error", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("network error"));
    render(<App />);
    await waitFor(() => expect(screen.getByText("Unavailable")).toBeInTheDocument());
  });
});
