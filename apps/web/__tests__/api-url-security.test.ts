import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { buildApiUrl, isSensitiveQueryKey } from "@/lib/api/url";

describe("api url security", () => {
	const envSnapshot = { ...process.env };

	beforeEach(() => {
		process.env = {
			...envSnapshot,
			NEXT_PUBLIC_API_BASE_URL: "https://api.example.com",
		};
	});

	afterEach(() => {
		process.env = { ...envSnapshot };
	});

	it("detects sensitive query keys", () => {
		expect(isSensitiveQueryKey("session_token")).toBe(true);
		expect(isSensitiveQueryKey("api-key")).toBe(true);
		expect(isSensitiveQueryKey("cursor")).toBe(false);
	});

	it("blocks sensitive query keys from url construction", () => {
		expect(() =>
			buildApiUrl("/api/v1/videos", { session_token: "abc" }),
		).toThrow("ERR_SENSITIVE_QUERY_KEY:session_token");
	});

	it("keeps normal query parameters", () => {
		const url = buildApiUrl("/api/v1/videos", { limit: 20, cursor: "abc" });
		const parsed = new URL(url, "http://localhost");
		expect(parsed.pathname).toBe("/api/v1/videos");
		expect(parsed.searchParams.get("limit")).toBe("20");
		expect(parsed.searchParams.get("cursor")).toBe("abc");
		expect(parsed.searchParams.has("session_token")).toBe(false);
	});

	it("rejects non-root api paths", () => {
		expect(() => buildApiUrl("api/v1/videos")).toThrow("ERR_INVALID_API_PATH");
		expect(() => buildApiUrl("//evil.example.com/steal")).toThrow(
			"ERR_INVALID_API_PATH",
		);
		expect(() => buildApiUrl("https://evil.example.com/steal")).toThrow(
			"ERR_INVALID_API_PATH",
		);
	});
});
