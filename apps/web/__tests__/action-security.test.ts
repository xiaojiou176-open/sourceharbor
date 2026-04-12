import { beforeEach, describe, expect, it, vi } from "vitest";
import { z } from "zod";

const { cookiesMock } = vi.hoisted(() => ({
	cookiesMock: vi.fn(),
}));

vi.mock("next/headers", () => ({
	cookies: cookiesMock,
}));

import {
	assertActionSession,
	getActionSessionTokenForForm,
	isNextRedirectError,
	schemas,
	toActionErrorCode,
} from "@/app/action-security";

function buildEmptyCookieStore() {
	return {
		get: vi.fn(() => undefined),
	};
}

function expectParseFailure<T>(result: {
	success: boolean;
	error?: z.ZodError;
	data?: T;
}): z.ZodError {
	if (result.success) {
		throw new Error("Expected parse failure");
	}
	return result.error ?? new z.ZodError([]);
}

describe("action security session token", () => {
	beforeEach(() => {
		process.env.WEB_ACTION_SESSION_TOKEN = "server-secret-value";
		cookiesMock.mockResolvedValue(buildEmptyCookieStore());
	});

	it("issues signed form token instead of exposing raw secret", () => {
		const token = getActionSessionTokenForForm();

		expect(token).toContain(".");
		expect(token).not.toBe(process.env.WEB_ACTION_SESSION_TOKEN);
	});

	it("accepts valid signed form token", async () => {
		const formData = new FormData();
		formData.set("session_token", getActionSessionTokenForForm());

		await expect(assertActionSession(formData)).resolves.toBeUndefined();
	});

	it("rejects malformed form token", async () => {
		const formData = new FormData();
		formData.set("session_token", "plain-text-secret");

		await expect(assertActionSession(formData)).rejects.toThrow(
			"ERR_AUTH_REQUIRED",
		);
	});

	it("falls back to NEXT_PUBLIC_WEB_ACTION_SESSION_TOKEN when the server-only token is absent", () => {
		delete process.env.WEB_ACTION_SESSION_TOKEN;
		process.env.NEXT_PUBLIC_WEB_ACTION_SESSION_TOKEN = "public-dev-token";

		const token = getActionSessionTokenForForm();
		expect(token).toContain(".");
		expect(token).not.toBe("public-dev-token");
	});
});

describe("isNextRedirectError", () => {
	it("matches Next redirect digest", () => {
		const err = Object.assign(new Error("redirect"), {
			digest: "NEXT_REDIRECT;/",
		});
		expect(isNextRedirectError(err)).toBe(true);
	});

	it("ignores non redirect errors", () => {
		expect(isNextRedirectError(new Error("boom"))).toBe(false);
	});
});

describe("action security URL schema hardening", () => {
	it("rejects javascript protocol for processVideo payload", () => {
		expect(() =>
			schemas.processVideo.parse({
				platform: "youtube",
				url: "javascript:alert(1)",
				mode: "full",
				force: false,
			}),
		).toThrow();
	});

	it("rejects javascript protocol for subscription source_url", () => {
		expect(() =>
			schemas.subscriptionUpsert.parse({
				platform: "youtube",
				source_type: "url",
				source_value: "https://example.com/source",
				adapter_type: "rss_generic",
				source_url: "javascript:alert(1)",
				rsshub_route: null,
				category: "misc",
				tags: [],
				priority: 50,
				enabled: true,
			}),
		).toThrow();
	});

	it("accepts rss platform for generalized source intake", () => {
		expect(() =>
			schemas.subscriptionUpsert.parse({
				platform: "rss",
				source_type: "url",
				source_value: "https://example.com/source",
				adapter_type: "rss_generic",
				source_url: "https://example.com/feed.xml",
				rsshub_route: null,
				category: "misc",
				tags: [],
				priority: 50,
				enabled: true,
			}),
		).not.toThrow();
	});
});

describe("toActionErrorCode field-level mapping", () => {
	it("maps url field issue to ERR_INVALID_URL", () => {
		const result = schemas.processVideo.safeParse({
			platform: "youtube",
			url: "not-a-url",
			mode: "full",
			force: false,
		});

		const error = expectParseFailure(result);
		expect(toActionErrorCode(error)).toBe("ERR_INVALID_URL");
	});

	it("maps email field issue to ERR_INVALID_EMAIL", () => {
		const result = schemas.notificationTest.safeParse({
			to_email: "not-an-email",
			subject: "subject",
			body: "body",
		});

		const error = expectParseFailure(result);
		expect(toActionErrorCode(error)).toBe("ERR_INVALID_EMAIL");
	});

	it("maps identifier field issue to ERR_INVALID_IDENTIFIER", () => {
		const schema = z.object({
			identifier: z.string().regex(/^[A-Z]+$/),
		});
		const result = schema.safeParse({
			identifier: "123",
		});

		const error = expectParseFailure(result);
		expect(toActionErrorCode(error)).toBe("ERR_INVALID_IDENTIFIER");
	});

	it("falls back to ERR_INVALID_INPUT when path is not recognized", () => {
		const result = schemas.pollIngest.safeParse({
			platform: "youtube",
			max_new_videos: "invalid-number",
		});

		const error = expectParseFailure(result);
		expect(toActionErrorCode(error)).toBe("ERR_INVALID_INPUT");
	});
});

describe("notificationConfig semantic validation", () => {
	it("parses empty daily_digest_hour_utc as null instead of 0", () => {
		const parsed = schemas.notificationConfig.parse({
			enabled: false,
			to_email: "",
			daily_digest_enabled: false,
			daily_digest_hour_utc: "",
			failure_alert_enabled: false,
		});

		expect(parsed.daily_digest_hour_utc).toBeNull();
		expect(parsed.to_email).toBeNull();
	});

	it("requires daily_digest_hour_utc when daily_digest_enabled=true", () => {
		const result = schemas.notificationConfig.safeParse({
			enabled: false,
			to_email: null,
			daily_digest_enabled: true,
			daily_digest_hour_utc: "",
			failure_alert_enabled: false,
		});

		const error = expectParseFailure(result);
		expect(toActionErrorCode(error)).toBe("ERR_DAILY_DIGEST_HOUR_REQUIRED");
	});

	it("requires to_email when enabled=true", () => {
		const result = schemas.notificationConfig.safeParse({
			enabled: true,
			to_email: "",
			daily_digest_enabled: false,
			daily_digest_hour_utc: null,
			failure_alert_enabled: false,
		});

		const error = expectParseFailure(result);
		expect(toActionErrorCode(error)).toBe("ERR_NOTIFICATION_EMAIL_REQUIRED");
	});
});
