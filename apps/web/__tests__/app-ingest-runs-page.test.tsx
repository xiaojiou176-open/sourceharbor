import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import IngestRunsPage from "@/app/ingest-runs/page";

const mockListIngestRuns = vi.fn();
const mockGetIngestRun = vi.fn();

vi.mock("next/link", () => ({
	default: ({
		href,
		children,
		...rest
	}: {
		href: string;
		children: React.ReactNode;
	}) => (
		<a href={href} {...rest}>
			{children}
		</a>
	),
}));

vi.mock("@/lib/api/client", () => ({
	apiClient: {
		listIngestRuns: (...args: unknown[]) => mockListIngestRuns(...args),
		getIngestRun: (...args: unknown[]) => mockGetIngestRun(...args),
	},
}));

describe("ingest runs page", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("renders recent runs and selected run detail", async () => {
		mockListIngestRuns.mockResolvedValue([
			{
				id: "run-1",
				subscription_id: null,
				workflow_id: "wf-1",
				platform: "youtube",
				max_new_videos: 10,
				status: "queued",
				jobs_created: 2,
				candidates_count: 3,
				feeds_polled: 1,
				entries_fetched: 4,
				entries_normalized: 4,
				ingest_events_created: 3,
				ingest_event_duplicates: 1,
				job_duplicates: 0,
				error_message: null,
				created_at: "2026-03-29T00:00:00Z",
				updated_at: "2026-03-29T00:00:00Z",
				completed_at: null,
			},
		]);
		mockGetIngestRun.mockResolvedValue({
			id: "run-1",
			subscription_id: null,
			workflow_id: "wf-1",
			platform: "youtube",
			max_new_videos: 10,
			status: "queued",
			jobs_created: 2,
			candidates_count: 3,
			feeds_polled: 1,
			entries_fetched: 4,
			entries_normalized: 4,
			ingest_events_created: 3,
			ingest_event_duplicates: 1,
			job_duplicates: 0,
			error_message: null,
			created_at: "2026-03-29T00:00:00Z",
			updated_at: "2026-03-29T00:00:00Z",
			completed_at: null,
			requested_by: null,
			requested_trace_id: null,
			filters_json: null,
			items: [
				{
					id: "item-1",
					subscription_id: null,
					video_id: "video-1",
					job_id: "job-1",
					ingest_event_id: null,
					platform: "youtube",
					video_uid: "yt-1",
					source_url: "https://example.com/watch?v=1",
					title: "Video One",
					published_at: null,
					entry_hash: null,
					pipeline_mode: "full",
					content_type: "video",
					item_status: "queued",
					created_at: "2026-03-29T00:00:00Z",
					updated_at: "2026-03-29T00:00:00Z",
				},
			],
		});

		render(await IngestRunsPage({ searchParams: { run_id: "run-1" } }));

		expect(mockListIngestRuns).toHaveBeenCalledWith({ limit: 10 });
		expect(mockGetIngestRun).toHaveBeenCalledWith("run-1");
		expect(
			screen.getByRole("heading", { name: "Recent ingest runs" }),
		).toBeInTheDocument();
		expect(screen.getByRole("link", { name: "run-1" })).toHaveAttribute(
			"href",
			"/ingest-runs?run_id=run-1",
		);
		expect(screen.getByText("Run detail")).toBeInTheDocument();
		expect(screen.getByRole("link", { name: "job-1" })).toHaveAttribute(
			"href",
			"/jobs?job_id=job-1",
		);
		expect(screen.getByText("Video One")).toBeInTheDocument();
	});
});
