export type FlashStatus = "success" | "error";

const FLASH_MESSAGES: Record<string, string> = {
	POLL_INGEST_OK: "Ingestion job queued.",
	PROCESS_VIDEO_OK: "Processing job created.",
	SUBSCRIPTION_CREATED: "Subscription created.",
	SUBSCRIPTION_UPDATED: "Subscription updated.",
	SUBSCRIPTION_DELETED: "Subscription deleted.",
	NOTIFICATION_CONFIG_SAVED: "Notification settings saved.",
	NOTIFICATION_TEST_SENT: "Test notification sent.",
	ERR_AUTH_REQUIRED: "Your session expired. Refresh the page and try again.",
	ERR_INVALID_INPUT: "The input is invalid. Review the fields and try again.",
	ERR_INVALID_URL:
		"The URL is invalid. Enter an address that starts with http:// or https://.",
	ERR_INVALID_EMAIL:
		"The email address is invalid. Enter a valid email address.",
	ERR_INVALID_IDENTIFIER: "The identifier format is invalid.",
	ERR_NOTIFICATION_EMAIL_REQUIRED:
		"A recipient email is required when notifications are enabled.",
	ERR_DAILY_DIGEST_HOUR_REQUIRED:
		"Set a UTC hour when the daily digest is enabled.",
	ERR_SENSITIVE_QUERY_KEY:
		"The request contains a sensitive query field and was blocked by the client.",
	ERR_REQUEST_FAILED: "The request failed. Please try again later.",
};

export function getFlashMessage(code: string): string {
	const normalized = code.trim().toUpperCase().split(":")[0] ?? "";
	if (!normalized) {
		return FLASH_MESSAGES.ERR_REQUEST_FAILED;
	}
	return FLASH_MESSAGES[normalized] ?? FLASH_MESSAGES.ERR_REQUEST_FAILED;
}

export function toFlashQuery(status: FlashStatus, code: string): string {
	const query = new URLSearchParams({
		status,
		code: code.trim().toUpperCase() || "ERR_REQUEST_FAILED",
	});
	return query.toString();
}

export function toErrorCode(error: unknown): string {
	if (error instanceof Error) {
		const normalized = error.message.trim().toUpperCase().split(":")[0] ?? "";
		if (normalized.startsWith("ERR_")) {
			return normalized;
		}
	}
	return "ERR_REQUEST_FAILED";
}
