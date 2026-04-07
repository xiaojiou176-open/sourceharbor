"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import {
	assertActionSession,
	isNextRedirectError,
	schemas,
	toActionErrorCode,
} from "@/app/action-security";
import { toFlashQuery } from "@/app/flash-message";
import { apiClient } from "@/lib/api/client";

function getServerWriteToken(): string | null {
	return process.env.SOURCE_HARBOR_API_KEY?.trim() || null;
}

function statusUrl(status: "success" | "error", code: string): string {
	return `/settings?${toFlashQuery(status, code)}`;
}

function toOptionalString(value: FormDataEntryValue | null): string | null {
	if (typeof value !== "string") {
		return null;
	}
	const trimmed = value.trim();
	return trimmed.length > 0 ? trimmed : null;
}

export async function updateNotificationConfigAction(formData: FormData) {
	try {
		await assertActionSession(formData);
		const payload = schemas.notificationConfig.parse({
			enabled: formData.get("enabled") === "on",
			to_email: toOptionalString(formData.get("to_email")),
			daily_digest_enabled: formData.get("daily_digest_enabled") === "on",
			daily_digest_hour_utc: toOptionalString(
				formData.get("daily_digest_hour_utc"),
			),
			failure_alert_enabled: formData.get("failure_alert_enabled") === "on",
		});

		await apiClient.updateNotificationConfig(
			{
				enabled: payload.enabled,
				to_email: payload.to_email,
				daily_digest_enabled: payload.daily_digest_enabled,
				daily_digest_hour_utc: payload.daily_digest_hour_utc,
				failure_alert_enabled: payload.failure_alert_enabled,
			},
			{ writeAccessToken: getServerWriteToken() },
		);

		revalidatePath("/settings");
		redirect(statusUrl("success", "NOTIFICATION_CONFIG_SAVED"));
	} catch (error) {
		if (isNextRedirectError(error)) {
			throw error;
		}
		redirect(statusUrl("error", toActionErrorCode(error)));
	}
}

export async function sendTestNotificationAction(formData: FormData) {
	try {
		await assertActionSession(formData);
		const payload = schemas.notificationTest.parse({
			to_email: toOptionalString(formData.get("to_email")),
			subject: toOptionalString(formData.get("subject")),
			body: toOptionalString(formData.get("body")),
		});

		await apiClient.sendNotificationTest(
			{
				to_email: payload.to_email,
				subject: payload.subject,
				body: payload.body,
			},
			{ writeAccessToken: getServerWriteToken() },
		);

		revalidatePath("/settings");
		redirect(statusUrl("success", "NOTIFICATION_TEST_SENT"));
	} catch (error) {
		if (isNextRedirectError(error)) {
			throw error;
		}
		redirect(statusUrl("error", toActionErrorCode(error)));
	}
}
