import { describe, expect, it } from "vitest";

import { getFlashMessage, toErrorCode } from "@/app/flash-message";

describe("flash-message mapping", () => {
	it("maps unknown code to generic message", () => {
		expect(getFlashMessage("UNKNOWN")).toBe(
			"The request failed. Please try again later.",
		);
	});

	it("maps field-level codes to actionable messages", () => {
		expect(getFlashMessage("ERR_INVALID_URL")).toBe(
			"The URL is invalid. Enter an address that starts with http:// or https://.",
		);
		expect(getFlashMessage("ERR_INVALID_EMAIL")).toBe(
			"The email address is invalid. Enter a valid email address.",
		);
		expect(getFlashMessage("ERR_INVALID_IDENTIFIER")).toBe(
			"The identifier format is invalid.",
		);
		expect(getFlashMessage("ERR_NOTIFICATION_EMAIL_REQUIRED")).toBe(
			"A recipient email is required when notifications are enabled.",
		);
		expect(getFlashMessage("ERR_DAILY_DIGEST_HOUR_REQUIRED")).toBe(
			"Set a UTC hour when the daily digest is enabled.",
		);
	});

	it("extracts only internal error code from Error", () => {
		expect(toErrorCode(new Error("ERR_INVALID_INPUT"))).toBe(
			"ERR_INVALID_INPUT",
		);
		expect(toErrorCode(new Error("https://example.com failed"))).toBe(
			"ERR_REQUEST_FAILED",
		);
	});
});
