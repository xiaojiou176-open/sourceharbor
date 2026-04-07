import { afterEach, describe, expect, it, vi } from "vitest";

import {
	buildApiUrl,
	buildApiUrlWithOptions,
	buildArtifactAssetUrl,
	resolveApiBaseUrl,
	sanitizeExternalUrl,
} from "@/lib/api/url";

describe("api url core", () => {
	const envSnapshot = { ...process.env };

	afterEach(() => {
		process.env = { ...envSnapshot };
		vi.restoreAllMocks();
	});

	it("uses NEXT_PUBLIC_API_BASE_URL and trims trailing slash", () => {
		process.env.NEXT_PUBLIC_API_BASE_URL = "https://api.example.com/";

		expect(resolveApiBaseUrl()).toBe("https://api.example.com");
	});

	it("throws when base url is missing without fallback", () => {
		delete process.env.NEXT_PUBLIC_API_BASE_URL;

		expect(() => resolveApiBaseUrl({ strict: true })).toThrow(
			"API base URL is not configured",
		);
	});

	it("does not fallback to SOURCE_HARBOR_API_BASE_URL", () => {
		delete process.env.NEXT_PUBLIC_API_BASE_URL;
		process.env.SOURCE_HARBOR_API_BASE_URL = "https://fallback.example.com";

		expect(() => resolveApiBaseUrl({ strict: true })).toThrow(
			"Set NEXT_PUBLIC_API_BASE_URL",
		);
	});

	it("falls back to localhost when allowed", () => {
		delete process.env.NEXT_PUBLIC_API_BASE_URL;
		delete process.env.API_PORT;

		expect(resolveApiBaseUrl()).toBe("http://127.0.0.1:9000");
	});

	it("uses API_PORT for local fallback when provided", () => {
		delete process.env.NEXT_PUBLIC_API_BASE_URL;
		process.env.API_PORT = "18000";

		expect(resolveApiBaseUrl()).toBe("http://127.0.0.1:18000");
	});

	it("rejects invalid or non-http base urls", () => {
		process.env.NEXT_PUBLIC_API_BASE_URL = "api.local";
		expect(() => resolveApiBaseUrl()).toThrow("Invalid API base URL");

		process.env.NEXT_PUBLIC_API_BASE_URL = "ftp://api.example.com";
		expect(() => resolveApiBaseUrl()).toThrow("Invalid API base URL protocol");
	});

	it("rejects base url with path/search/hash/credentials", () => {
		// Build the credentialed URL at runtime so secret scanners do not treat the
		// negative-test fixture as a committed credential literal.
		process.env.NEXT_PUBLIC_API_BASE_URL = [
			"https://user",
			"pass@api.example.com",
		].join(":");
		expect(() => resolveApiBaseUrl()).toThrow(
			"Invalid API base URL credentials",
		);

		process.env.NEXT_PUBLIC_API_BASE_URL = "https://api.example.com/v1";
		expect(() => resolveApiBaseUrl()).toThrow("Invalid API base URL path");

		process.env.NEXT_PUBLIC_API_BASE_URL = "https://api.example.com?x=1";
		expect(() => resolveApiBaseUrl()).toThrow("Invalid API base URL suffix");

		process.env.NEXT_PUBLIC_API_BASE_URL = "https://api.example.com#frag";
		expect(() => resolveApiBaseUrl()).toThrow("Invalid API base URL suffix");
	});

	it("builds url and skips nullish/empty query values", () => {
		process.env.NEXT_PUBLIC_API_BASE_URL = "https://api.example.com";

		const result = buildApiUrl("/api/v1/feed", {
			limit: 10,
			has_more: false,
			cursor: "",
			since: null,
			source: undefined,
		});

		const parsed = new URL(result);
		expect(parsed.searchParams.get("limit")).toBe("10");
		expect(parsed.searchParams.get("has_more")).toBe("false");
		expect(parsed.searchParams.has("cursor")).toBe(false);
		expect(parsed.searchParams.has("since")).toBe(false);
		expect(parsed.searchParams.has("source")).toBe(false);
	});

	it("throws when buildApiUrl is called without NEXT_PUBLIC_API_BASE_URL", () => {
		delete process.env.NEXT_PUBLIC_API_BASE_URL;

		expect(() =>
			buildApiUrlWithOptions("/api/v1/feed", undefined, { strict: true }),
		).toThrow("API base URL is not configured");
	});

	it("builds artifact asset url with required query keys", () => {
		process.env.NEXT_PUBLIC_API_BASE_URL = "https://api.example.com";

		const url = buildArtifactAssetUrl("job-1", "summary.md");
		const parsed = new URL(url);
		expect(parsed.pathname).toBe("/api/v1/artifacts/assets");
		expect(parsed.searchParams.get("job_id")).toBe("job-1");
		expect(parsed.searchParams.get("path")).toBe("summary.md");
	});

	it("sanitizes only absolute http(s) urls", () => {
		expect(sanitizeExternalUrl(" https://example.com/a?b=1 ")).toBe(
			"https://example.com/a?b=1",
		);
		expect(sanitizeExternalUrl("http://example.com")).toBe(
			"http://example.com/",
		);
		expect(sanitizeExternalUrl("javascript:alert(1)")).toBeNull();
		expect(sanitizeExternalUrl("/relative/path")).toBeNull();
		expect(
			sanitizeExternalUrl(["https://user", "pass@example.com/x"].join(":")),
		).toBeNull();
		expect(sanitizeExternalUrl("   ")).toBeNull();
	});
});
