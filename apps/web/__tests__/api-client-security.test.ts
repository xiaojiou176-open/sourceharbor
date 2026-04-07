import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/lib/api/client";

describe("apiClient identifier hardening", () => {
	const envSnapshot = { ...process.env };

	beforeEach(() => {
		process.env = {
			...envSnapshot,
			NEXT_PUBLIC_API_BASE_URL: "https://api.example.com",
		};
	});

	afterEach(() => {
		process.env = { ...envSnapshot };
		vi.restoreAllMocks();
	});

	it("rejects unsafe delete id containing path separators", () => {
		expect(() => apiClient.deleteSubscription("../etc/passwd")).toThrow(
			"ERR_INVALID_IDENTIFIER",
		);
	});

	it("encodes safe id for delete request path", async () => {
		const fetchSpy = vi
			.spyOn(globalThis, "fetch")
			.mockResolvedValue(new Response(null, { status: 204 }));

		await apiClient.deleteSubscription("ab:12.cd");

		expect(fetchSpy).toHaveBeenCalledTimes(1);
		const [url] = fetchSpy.mock.calls[0];
		expect(String(url)).toContain("/api/v1/subscriptions/ab%3A12.cd");
	});

	it("rejects artifact lookup with non-http(s) video_url", () => {
		expect(() =>
			apiClient.getArtifactMarkdown({
				video_url: "javascript:alert(1)",
				include_meta: true,
			}),
		).toThrow("ERR_INVALID_INPUT");
	});

	it("rejects artifact lookup video_url with embedded credentials", () => {
		expect(() =>
			apiClient.getArtifactMarkdown({
				video_url: ["https://user", "pass@example.com/watch?v=1"].join(":"),
				include_meta: true,
			}),
		).toThrow("ERR_INVALID_INPUT");
	});

	it("accepts https artifact lookup video_url", async () => {
		const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
			new Response(JSON.stringify({ markdown: "", meta: null }), {
				status: 200,
			}),
		);

		await apiClient.getArtifactMarkdown({
			video_url: "https://example.com/watch?v=1",
			include_meta: true,
		});

		const [url] = fetchSpy.mock.calls[0];
		expect(String(url)).toContain(
			"video_url=https%3A%2F%2Fexample.com%2Fwatch%3Fv%3D1",
		);
	});
});
