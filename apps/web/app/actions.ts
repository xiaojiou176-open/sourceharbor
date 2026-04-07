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
import type { Platform } from "@/lib/api/types";

function getServerWriteToken(): string | null {
	return process.env.SOURCE_HARBOR_API_KEY?.trim() || null;
}

function statusUrl(
	pathname: string,
	status: "success" | "error",
	code: string,
): string {
	return `${pathname}?${toFlashQuery(status, code)}`;
}

export async function pollIngestAction(formData: FormData) {
	try {
		await assertActionSession(formData);
		const payload = schemas.pollIngest.parse({
			platform: String(formData.get("platform") ?? "").trim() || undefined,
			max_new_videos: String(formData.get("max_new_videos") ?? "50"),
		});
		const result = await apiClient.pollIngest(
			{
				platform: payload.platform as Platform | undefined,
				max_new_videos: payload.max_new_videos,
			},
			{ writeAccessToken: getServerWriteToken() },
		);
		revalidatePath("/");
		revalidatePath("/jobs");
		void result;
		redirect(statusUrl("/", "success", "POLL_INGEST_OK"));
	} catch (error) {
		if (isNextRedirectError(error)) {
			throw error;
		}
		redirect(statusUrl("/", "error", toActionErrorCode(error)));
	}
}

export async function processVideoAction(formData: FormData) {
	try {
		await assertActionSession(formData);
		const payload = schemas.processVideo.parse({
			platform: String(formData.get("platform") ?? "youtube").trim(),
			url: String(formData.get("url") ?? "").trim(),
			mode: String(formData.get("mode") ?? "full").trim(),
			force: formData.get("force") === "on",
		});
		await apiClient.processVideo(
			{
				video: { platform: payload.platform as Platform, url: payload.url },
				mode: payload.mode,
				force: payload.force,
			},
			{ writeAccessToken: getServerWriteToken() },
		);

		revalidatePath("/");
		revalidatePath("/jobs");
		revalidatePath("/feed");
		redirect(statusUrl("/", "success", "PROCESS_VIDEO_OK"));
	} catch (error) {
		if (isNextRedirectError(error)) {
			throw error;
		}
		redirect(statusUrl("/", "error", toActionErrorCode(error)));
	}
}
