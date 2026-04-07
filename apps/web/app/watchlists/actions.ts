"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { z } from "zod";

import {
	assertActionSession,
	isNextRedirectError,
	toActionErrorCode,
} from "@/app/action-security";
import { toFlashQuery } from "@/app/flash-message";
import { apiClient } from "@/lib/api/client";

const watchlistSchema = z.object({
	id: z.string().trim().min(1).max(128).nullable(),
	name: z.string().trim().min(1).max(120),
	matcher_type: z.enum(["topic_key", "claim_kind", "platform", "source_match"]),
	matcher_value: z.string().trim().min(1).max(200),
	delivery_channel: z.enum(["dashboard", "email"]).default("dashboard"),
	enabled: z.boolean().default(true),
});

function getServerWriteToken(): string | null {
	return process.env.SOURCE_HARBOR_API_KEY?.trim() || null;
}

function statusUrl(status: "success" | "error", code: string): string {
	return `/watchlists?${toFlashQuery(status, code)}`;
}

function toOptionalString(value: FormDataEntryValue | null): string | null {
	if (typeof value !== "string") {
		return null;
	}
	const trimmed = value.trim();
	return trimmed.length > 0 ? trimmed : null;
}

export async function upsertWatchlistAction(formData: FormData) {
	try {
		await assertActionSession(formData);
		const payload = watchlistSchema.parse({
			id: toOptionalString(formData.get("id")),
			name: formData.get("name"),
			matcher_type: formData.get("matcher_type"),
			matcher_value: formData.get("matcher_value"),
			delivery_channel: formData.get("delivery_channel") || "dashboard",
			enabled: formData.get("enabled") === "on",
		});

		const response = await apiClient.upsertWatchlist(
			{
				id: payload.id,
				name: payload.name,
				matcher_type: payload.matcher_type,
				matcher_value: payload.matcher_value,
				delivery_channel: payload.delivery_channel,
				enabled: payload.enabled,
			},
			{ writeAccessToken: getServerWriteToken() },
		);

		revalidatePath("/watchlists");
		revalidatePath("/trends");
		revalidatePath("/briefings");
		redirect(
			`/watchlists?watchlist_id=${encodeURIComponent(response.id)}&${toFlashQuery("success", "WATCHLIST_SAVED")}`,
		);
	} catch (error) {
		if (isNextRedirectError(error)) {
			throw error;
		}
		redirect(statusUrl("error", toActionErrorCode(error)));
	}
}

export async function deleteWatchlistAction(formData: FormData) {
	try {
		await assertActionSession(formData);
		const watchlistId = z
			.string()
			.trim()
			.min(1)
			.max(128)
			.parse(formData.get("watchlist_id"));
		await apiClient.deleteWatchlist(watchlistId, {
			writeAccessToken: getServerWriteToken(),
		});
		revalidatePath("/watchlists");
		revalidatePath("/trends");
		revalidatePath("/briefings");
		redirect(statusUrl("success", "WATCHLIST_DELETED"));
	} catch (error) {
		if (isNextRedirectError(error)) {
			throw error;
		}
		redirect(statusUrl("error", toActionErrorCode(error)));
	}
}
