import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ReaderDocumentPage from "@/app/reader/[documentId]/page";
import ReaderPage from "@/app/reader/page";

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
			screen.getByText(
				"Read the strongest finished unit before you touch the operator rails",
			),
		).toBeInTheDocument();
		expect(
			screen.getByRole("heading", { name: "AI Agents", level: 3 }),
		).toBeInTheDocument();
		expect(screen.getAllByText("Yellow warning").length).toBeGreaterThanOrEqual(
			1,
		);
		expect(
			screen.getByText("Read 1 published reader documents."),
		).toBeInTheDocument();
		expect(
			screen.getByRole("link", { name: "Continue reading" }),
		).toHaveAttribute("href", "/reader/doc-1");
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
			},
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
		expect(screen.getByText("Source universe")).toBeInTheDocument();
		expect(screen.getAllByText("Agents recap").length).toBeGreaterThanOrEqual(
			1,
		);
		expect(screen.getByTestId("reader-source-drawer")).toHaveTextContent(
			"AI Agents",
		);
		expect(screen.getAllByTestId("markdown-preview")[0]).toHaveTextContent(
			"# AI Agents",
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
				name: "Reader specimen edition",
				level: 1,
			}),
		).toBeInTheDocument();
		expect(
			screen.getAllByText("Specimen edition").length,
		).toBeGreaterThanOrEqual(1);
		expect(screen.getAllByText("Yellow warning").length).toBeGreaterThanOrEqual(
			1,
		);
		expect(screen.getByTestId("reader-source-drawer")).toHaveTextContent(
			"Reader specimen edition",
		);
	});
});
