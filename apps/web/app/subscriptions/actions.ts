"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import {
	assertActionSession,
	isNextRedirectError,
	parseIdentifier,
	schemas,
	toActionErrorCode,
} from "@/app/action-security";
import { toFlashQuery } from "@/app/flash-message";
import { apiClient } from "@/lib/api/client";
import type {
	Platform,
	SourceType,
	SubscriptionAdapterType,
	SubscriptionCategory,
} from "@/lib/api/types";

function getServerWriteToken(): string | null {
	return process.env.SOURCE_HARBOR_API_KEY?.trim() || null;
}

function statusUrl(status: "success" | "error", code: string): string {
	return `/subscriptions?${toFlashQuery(status, code)}`;
}

export async function upsertSubscriptionAction(formData: FormData) {
	try {
		await assertActionSession(formData);
		const sourceUrlRaw = String(formData.get("source_url") ?? "").trim();
		const rsshubRouteRaw = String(formData.get("rsshub_route") ?? "").trim();
		const tagsRaw = String(formData.get("tags") ?? "").trim();
		const payload = schemas.subscriptionUpsert.parse({
			platform: String(formData.get("platform") ?? "youtube").trim(),
			source_type: String(formData.get("source_type") ?? "url").trim(),
			source_value: String(formData.get("source_value") ?? "").trim(),
			adapter_type: String(
				formData.get("adapter_type") ?? "rsshub_route",
			).trim(),
			source_url: sourceUrlRaw || null,
			rsshub_route: rsshubRouteRaw || null,
			category: String(formData.get("category") ?? "misc").trim(),
			tags: tagsRaw
				.split(",")
				.map((item) => item.trim())
				.filter((item) => item.length > 0),
			priority: String(formData.get("priority") ?? "50"),
			enabled: formData.get("enabled") === "on",
		});

		const result = await apiClient.upsertSubscription(
			{
				platform: payload.platform as Platform,
				source_type: payload.source_type as SourceType,
				source_value: payload.source_value,
				adapter_type: payload.adapter_type as SubscriptionAdapterType,
				source_url: payload.source_url,
				rsshub_route: payload.rsshub_route,
				category: payload.category as SubscriptionCategory,
				tags: payload.tags,
				priority: payload.priority,
				enabled: payload.enabled,
			},
			{ writeAccessToken: getServerWriteToken() },
		);

		revalidatePath("/subscriptions");
		redirect(
			statusUrl(
				"success",
				result.created ? "SUBSCRIPTION_CREATED" : "SUBSCRIPTION_UPDATED",
			),
		);
	} catch (error) {
		if (isNextRedirectError(error)) {
			throw error;
		}
		redirect(statusUrl("error", toActionErrorCode(error)));
	}
}

export async function deleteSubscriptionAction(formData: FormData) {
	try {
		await assertActionSession(formData);
		const id = parseIdentifier(String(formData.get("id") ?? ""));
		await apiClient.deleteSubscription(id, {
			writeAccessToken: getServerWriteToken(),
		});
		revalidatePath("/subscriptions");
		redirect(statusUrl("success", "SUBSCRIPTION_DELETED"));
	} catch (error) {
		if (isNextRedirectError(error)) {
			throw error;
		}
		redirect(statusUrl("error", toActionErrorCode(error)));
	}
}

export async function deleteSubscriptionByIdAction(id: string) {
	try {
		await apiClient.deleteSubscription(parseIdentifier(id), {
			writeAccessToken: getServerWriteToken(),
		});
		revalidatePath("/subscriptions");
		return { ok: true as const };
	} catch (error) {
		throw new Error(toActionErrorCode(error));
	}
}

export async function batchUpdateSubscriptionCategoryAction(payload: {
	ids: string[];
	category: SubscriptionCategory;
}) {
	try {
		const ids = payload.ids.map((id) => parseIdentifier(id));
		const category = schemas.subscriptionUpsert.shape.category.parse(
			payload.category,
		);
		const result = await apiClient.batchUpdateSubscriptionCategory(
			{ ids, category },
			{ writeAccessToken: getServerWriteToken() },
		);
		revalidatePath("/subscriptions");
		return result;
	} catch (error) {
		throw new Error(toActionErrorCode(error));
	}
}
