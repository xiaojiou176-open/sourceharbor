import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ReaderDocumentPage from "@/app/reader/[documentId]/page";
import ReaderPage from "@/app/reader/page";
import { DEMO_READER_DOCUMENT_ID } from "@/lib/reader/demo-document";

const mockListPublishedReaderDocuments = vi.fn();
const mockGetNavigationBrief = vi.fn();
const mockGetPublishedReaderDocument = vi.fn();

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

vi.mock("@/components/markdown-preview", () => ({
	MarkdownPreview: ({ markdown }: { markdown: string }) => (
		<div data-testid="markdown-preview">{markdown}</div>
	),
}));

vi.mock("@/components/source-contribution-drawer", () => ({
	SourceContributionDrawer: ({ document }: { document: { title: string } }) => (
		<div data-testid="reader-source-drawer">{document.title}</div>
	),
}));

vi.mock("@/components/reader-repair-panel", () => ({
	ReaderRepairPanel: ({
		documentId,
		repairHistoryCount,
	}: {
		documentId: string;
		repairHistoryCount: number;
	}) => (
		<div data-testid="reader-repair-panel">
			{documentId}:{repairHistoryCount}
		</div>
	),
}));

vi.mock("@/lib/api/client", () => ({
	apiClient: {
		listPublishedReaderDocuments: (...args: unknown[]) =>
			mockListPublishedReaderDocuments(...args),
		getNavigationBrief: (...args: unknown[]) => mockGetNavigationBrief(...args),
		getPublishedReaderDocument: (...args: unknown[]) =>
			mockGetPublishedReaderDocument(...args),
	},
}));

describe("reader pages", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("renders reader home with navigation brief and published doc cards", async () => {
		mockListPublishedReaderDocuments.mockResolvedValue([
			{
				id: "doc-1",
				slug: "ai-agents-2026-04-09-v1",
				window_id: "2026-04-09@America/Los_Angeles",
				title: "AI Agents",
				summary: "Merged reader doc",
				materialization_mode: "merge_then_polish",
				version: 1,
				published_with_gap: true,
				source_item_count: 2,
				topic_label: "AI Agents",
				consumption_batch_id: "batch-1",
				source_refs: [
					{
						source_item_id: "src-1",
						title: "Agents recap",
						digest_preview: "Agents one preview",
					},
				],
			},
			{
				id: "doc-2",
				slug: "ai-agents-2026-04-09-v2",
				window_id: "2026-04-09@America/Los_Angeles",
				title: "AI Agents follow-up",
				summary: "Singleton reader doc",
				materialization_mode: "singleton_polish",
				version: 1,
				published_with_gap: false,
				source_item_count: 1,
				topic_label: "AI Agents",
				consumption_batch_id: "batch-2",
				source_refs: [],
			},
		]);
		mockGetNavigationBrief.mockResolvedValue({
			brief_kind: "sourceharbor_navigation_brief_v1",
			generated_at: "2026-04-09T00:00:00Z",
			window_id: "2026-04-09@America/Los_Angeles",
			document_count: 1,
			published_with_gap_count: 1,
			summary: "Read 1 published reader documents.",
			items: [
				{
					document_id: "doc-1",
					title: "AI Agents",
					summary: "Merged reader doc",
					route: "/reader/doc-1",
				},
			],
		});

		render(await ReaderPage());

		expect(
			screen.getByRole("heading", {
				name: "AI Agents follow-up",
				level: 1,
			}),
		).toBeInTheDocument();
		expect(
			screen.getByRole("heading", { name: "AI Agents", level: 3 }),
		).toBeInTheDocument();
		expect(screen.getAllByText("Read with care").length).toBeGreaterThanOrEqual(
			1,
		);
		expect(
			screen.getByRole("link", { name: "Continue reading" }),
		).toHaveAttribute("href", "/reader/doc-2");
		expect(screen.getByText("Up next")).toBeInTheDocument();
		expect(screen.getByRole("link", { name: "Open story" })).toHaveAttribute(
			"href",
			"/reader/doc-1",
		);
	});

	it("renders reader detail with warning banner and source drawer", async () => {
		mockGetPublishedReaderDocument.mockResolvedValue({
			id: "doc-1",
			title: "AI Agents",
			window_id: "2026-04-09@America/Los_Angeles",
			topic_label: "AI Agents",
			source_item_count: 2,
			published_with_gap: true,
			materialization_mode: "merge_then_polish",
			version: 2,
			summary: "Merged reader doc",
			markdown: "# AI Agents\n\nMerged reader doc",
			sections: [
				{ section_id: "summary", title: "Summary", source_item_ids: ["src-1"] },
			],
			source_refs: [{ source_item_id: "src-1", title: "Agents recap" }],
			coverage_ledger: {
				ledger_kind: "sourceharbor_coverage_ledger_v1",
				covered_source_count: 1,
				gap_source_count: 1,
				status: "gap_detected",
			},
			traceability_pack: {
				status: "gap_detected",
				section_contributions: [{ section_id: "summary" }],
				source_items: [{ source_item_id: "src-1" }],
				affected_source_item_ids: ["src-1"],
				evidence_routes: { job_bundle: ["/api/v1/jobs/job-1/bundle"] },
			},
			repair_history: [{ repair_mode: "patch" }],
			warning: { reasons: ["1 source missing digest"] },
			consumption_batch_id: "batch-1",
		});

		render(
			await ReaderDocumentPage({
				params: Promise.resolve({ documentId: "doc-1" }),
			}),
		);

		expect(screen.getAllByText("Yellow warning").length).toBeGreaterThanOrEqual(
			1,
		);
		expect(
			screen.getByRole("heading", { name: "AI Agents", level: 1 }),
		).toBeInTheDocument();
		expect(screen.getByText("Source notes and repair")).toBeInTheDocument();
		expect(screen.getByTestId("reader-source-drawer")).toHaveTextContent(
			"AI Agents",
		);
		expect(screen.getAllByTestId("markdown-preview")[0]).toHaveTextContent(
			"# AI Agents",
		);
		expect(
			screen.getByRole("link", { name: "Back to reader" }),
		).toHaveAttribute("href", "/reader");
		expect(screen.getByText(/Read the story first/i)).toBeInTheDocument();
		expect(screen.getByText("Source notes and repair")).toBeInTheDocument();
		expect(screen.getByTestId("reader-repair-panel")).toHaveTextContent(
			"doc-1:1",
		);
	});

	it("renders preview detail when the demo route is requested", async () => {
		render(
			await ReaderDocumentPage({
				params: Promise.resolve({ documentId: "demo" }),
			}),
		);

		expect(
			screen.getByRole("heading", {
				name: "What happens after the first prototype",
				level: 1,
			}),
		).toBeInTheDocument();
		expect(screen.getAllByText("Yellow warning").length).toBeGreaterThanOrEqual(
			1,
		);
		expect(screen.getByTestId("reader-source-drawer")).toHaveTextContent(
			"What happens after the first prototype",
		);
	});

	it("replaces a raw URL hero title with a reader-friendly fallback title", async () => {
		mockGetPublishedReaderDocument.mockResolvedValue({
			id: "doc-url",
			title: "https://www.youtube.com/watch?v=aqz-KE-bpKQ",
			window_id: "2026-04-14@America/Los_Angeles",
			topic_label: null,
			source_item_count: 1,
			published_with_gap: false,
			materialization_mode: "singleton_polish",
			version: 1,
			summary: "A polish-only reader document from youtube.",
			markdown: "# Story",
			sections: [],
			source_refs: [
				{
					source_item_id: "src-1",
					title: "https://www.youtube.com/watch?v=aqz-KE-bpKQ",
					platform: "youtube",
				},
			],
			coverage_ledger: {},
			traceability_pack: {},
			repair_history: [],
			warning: null,
			consumption_batch_id: "batch-url",
		});

		render(
			await ReaderDocumentPage({
				params: Promise.resolve({ documentId: "doc-url" }),
			}),
		);

		expect(
			screen.getByRole("heading", {
				name: "Reading note from youtube",
				level: 1,
			}),
		).toBeInTheDocument();
		expect(
			screen.queryByRole("heading", {
				name: "https://www.youtube.com/watch?v=aqz-KE-bpKQ",
				level: 1,
			}),
		).not.toBeInTheDocument();
	});

	it("renders an honest shelf error instead of pretending the shelf is empty", async () => {
		mockListPublishedReaderDocuments.mockRejectedValue(
			new Error("network failed"),
		);
		mockGetNavigationBrief.mockRejectedValue(new Error("network failed"));

		render(await ReaderPage());

		expect(
			screen.getByRole("heading", {
				name: "Reader shelf is temporarily unavailable",
				level: 1,
			}),
		).toBeInTheDocument();
		const alert = screen.getByRole("alert");
		expect(alert).toHaveTextContent("Reader shelf is temporarily unavailable");
		expect(
			within(alert).getByRole("link", { name: "Open specimen detail" }),
		).toHaveAttribute("href", `/reader/${DEMO_READER_DOCUMENT_ID}`);
		expect(
			within(alert).getByRole("link", { name: "Open ops desk" }),
		).toHaveAttribute("href", "/ops");
		expect(
			screen.queryByText("No published decks yet"),
		).not.toBeInTheDocument();
	});
});
