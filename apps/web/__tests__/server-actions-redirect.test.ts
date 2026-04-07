import { beforeEach, describe, expect, it, vi } from "vitest";

const { redirectMock } = vi.hoisted(() => ({
	redirectMock: vi.fn((url: string) => {
		const error = Object.assign(new Error("redirect"), {
			digest: `NEXT_REDIRECT;${url}`,
		});
		throw error;
	}),
}));

vi.mock("next/navigation", () => ({
	redirect: redirectMock,
}));

vi.mock("next/cache", () => ({
	revalidatePath: vi.fn(),
}));

import { pollIngestAction } from "@/app/actions";
import { apiClient } from "@/lib/api/client";

describe("server actions redirect behavior", () => {
	beforeEach(() => {
		vi.restoreAllMocks();
		redirectMock.mockClear();
		process.env.WEB_ACTION_SESSION_TOKEN = "";
	});

	it("preserves success redirect instead of converting to error redirect", async () => {
		vi.spyOn(apiClient, "pollIngest").mockResolvedValue({
			run_id: "run-1",
			workflow_id: "wf-1",
			status: "queued",
			enqueued: 1,
			candidates: [],
		});
		const formData = new FormData();
		formData.set("max_new_videos", "5");

		await expect(pollIngestAction(formData)).rejects.toMatchObject({
			digest: expect.stringContaining(
				"NEXT_REDIRECT;/?status=success&code=POLL_INGEST_OK",
			),
		});

		expect(redirectMock).toHaveBeenCalledWith(
			"/?status=success&code=POLL_INGEST_OK",
		);
	});

	it("redirects with mapped error code on API failures", async () => {
		vi.spyOn(apiClient, "pollIngest").mockRejectedValue(
			new Error("ERR_INVALID_INPUT"),
		);
		const formData = new FormData();

		await expect(pollIngestAction(formData)).rejects.toMatchObject({
			digest: expect.stringContaining(
				"NEXT_REDIRECT;/?status=error&code=ERR_INVALID_INPUT",
			),
		});

		expect(redirectMock).toHaveBeenCalledWith(
			"/?status=error&code=ERR_INVALID_INPUT",
		);
	});
});
