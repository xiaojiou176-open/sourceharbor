import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { getActionSessionTokenForForm } from "@/app/action-security";
import { MarkdownPreview } from "@/components/markdown-preview";
import { ReaderRepairPanel } from "@/components/reader-repair-panel";
import { SourceContributionDrawer } from "@/components/source-contribution-drawer";
import { Badge } from "@/components/ui/badge";
import { YellowWarningCard } from "@/components/yellow-warning-card";
import { apiClient } from "@/lib/api/client";
import {
	editorialMono,
	editorialSans,
	editorialSerif,
} from "@/lib/editorial-fonts";
import {
	buildDemoReaderDocument,
	DEMO_READER_DOCUMENT_ID,
} from "@/lib/reader/demo-document";
import { buildProductMetadata } from "@/lib/seo";
import { resolveReaderSourceIdentity } from "@/lib/source-identity";

type ReaderDetailPageProps = {
	params: Promise<{ documentId: string }> | { documentId: string };
};

function looksLikeRawUrl(value: string | null | undefined): boolean {
	const text = String(value || "")
		.trim()
		.toLowerCase();
	return text.startsWith("http://") || text.startsWith("https://");
}

function formatReaderHeroTitle(document: {
	title: string;
	topic_label?: string | null;
	materialization_mode: string;
	source_refs?: Array<Parameters<typeof resolveReaderSourceIdentity>[0]>;
}): string {
	const rawTitle = document.title.trim();
	if (!looksLikeRawUrl(rawTitle)) {
		return rawTitle || "Published document";
	}
	const topicLabel = String(document.topic_label || "").trim();
	if (topicLabel && !looksLikeRawUrl(topicLabel)) {
		return topicLabel;
	}
	const firstSource = Array.isArray(document.source_refs)
		? document.source_refs[0]
		: null;
	const sourceTitle = firstSource
		? resolveReaderSourceIdentity(firstSource).title
		: "";
	if (sourceTitle && !looksLikeRawUrl(sourceTitle)) {
		return sourceTitle;
	}
	if (firstSource?.platform) {
		return document.materialization_mode === "singleton_polish"
			? `Reading note from ${String(firstSource.platform).trim()}`
			: `Reading story from ${String(firstSource.platform).trim()}`;
	}
	return document.materialization_mode === "singleton_polish"
		? "Reading note"
		: "Published story";
}

export async function generateMetadata({
	params,
}: ReaderDetailPageProps): Promise<Metadata> {
	const resolved = await params;
	const isPreviewRoute = resolved.documentId === DEMO_READER_DOCUMENT_ID;
	return buildProductMetadata({
		title: isPreviewRoute
			? "Reader detail preview"
			: `Reader document ${resolved.documentId}`,
		description: isPreviewRoute
			? "Preview a sample reading page before the first live story lands."
			: "Finished story view with source notes and background detail when you want them.",
		route: "reader",
	});
}

export default async function ReaderDetailPage({
	params,
}: ReaderDetailPageProps) {
	const resolved = await params;
	const isPreviewRoute = resolved.documentId === DEMO_READER_DOCUMENT_ID;
	const document = isPreviewRoute
		? buildDemoReaderDocument()
		: await apiClient
				.getPublishedReaderDocument(resolved.documentId)
				.catch(() => null);

	if (!document) {
		notFound();
	}

	const sections = Array.isArray(document.sections) ? document.sections : [];
	const heroTitle = formatReaderHeroTitle(document);
	const warningReasons = Array.isArray(document.warning?.reasons)
		? document.warning.reasons
		: [];
	const repairHistory = Array.isArray(document.repair_history)
		? document.repair_history
		: [];
	const sessionToken = getActionSessionTokenForForm();
	const readingNote = document.published_with_gap
		? "Read the story first. Keep the warning in mind, then open notes only when you want provenance."
		: "Read the story first. Open sources, coverage, and repair only when you need them.";

	return (
		<div
			className={`mx-auto flex w-full max-w-[72rem] flex-col gap-10 px-4 py-8 md:px-6 ${editorialSans.className}`}
		>
			<section className="space-y-6">
				<div className="flex flex-wrap items-center gap-3 text-sm text-foreground/80">
					<Link
						href="/reader"
						className="inline-flex items-center gap-2 rounded-full border border-border/60 px-3 py-1 no-underline transition hover:bg-muted/40 visited:text-foreground"
						style={{ color: "var(--foreground)" }}
					>
						Back to reader
					</Link>
				</div>
				<div className="space-y-5">
					<div className="space-y-4">
						<div className="flex flex-wrap items-center gap-2">
							<Badge
								variant="outline"
								className={
									document.published_with_gap
										? "border-amber-500/45 bg-amber-500/12 text-amber-800"
										: undefined
								}
							>
								{resolved.documentId === DEMO_READER_DOCUMENT_ID
									? "Preview sample"
									: document.published_with_gap
										? "Read with care"
										: "Ready"}
							</Badge>
						</div>
						<h1
							data-route-heading
							tabIndex={-1}
							className={`max-w-4xl text-3xl leading-[1.02] tracking-tight [overflow-wrap:anywhere] sm:text-4xl md:text-5xl xl:text-6xl ${editorialSerif.className}`}
						>
							{heroTitle}
						</h1>
						<p className="max-w-4xl text-base leading-8 text-foreground/75">
							{document.summary ??
								"Read the story first. Source notes and background detail stay below for when you want a closer look."}
						</p>
					</div>
				</div>
			</section>

			<section id="reader-body" className="space-y-5">
				<article className="rounded-[2rem] border border-border/70 bg-background/95 shadow-sm">
					<div className="mx-auto max-w-[74ch] p-5 md:p-8">
						<MarkdownPreview markdown={document.markdown} />
					</div>
				</article>
			</section>

			<section id="reader-notes" className="space-y-4">
				<details className="rounded-[1.6rem] border border-border/70 bg-background/95 shadow-sm">
					<summary className="cursor-pointer list-none px-5 py-4">
						<div className="flex flex-wrap items-start justify-between gap-3">
							<div className="space-y-2">
								<p
									className={`text-[11px] uppercase tracking-[0.22em] text-muted-foreground ${editorialMono.className}`}
								>
									Notes later
								</p>
								<h2
									className={`text-2xl leading-tight text-foreground ${editorialSerif.className}`}
								>
									Source notes and repair
								</h2>
								<p className="max-w-3xl text-sm leading-6 text-muted-foreground">
									{readingNote}
								</p>
							</div>
							<div className="flex flex-wrap gap-2 text-sm">
								<Badge
									variant={
										document.published_with_gap ? "secondary" : "outline"
									}
								>
									{document.published_with_gap
										? "Read with care"
										: "Story notes"}
								</Badge>
							</div>
						</div>
					</summary>
					<div className="space-y-6 border-t border-border/60 px-5 pb-5 pt-4">
						{document.published_with_gap ? (
							<YellowWarningCard reasons={warningReasons} />
						) : null}

						<SourceContributionDrawer document={document} />

						{isPreviewRoute ? (
							<div className="rounded-2xl border border-border/60 bg-muted/15 p-4 text-sm leading-6 text-muted-foreground">
								This specimen only shows where note-taking and provenance will
								live. Live repair stays disabled until a real published reader
								document exists.
							</div>
						) : (
							<ReaderRepairPanel
								documentId={document.id}
								publishedWithGap={document.published_with_gap}
								repairHistoryCount={repairHistory.length}
								sectionIds={sections.map((section) => section.section_id)}
								sessionToken={sessionToken}
							/>
						)}
					</div>
				</details>
			</section>
		</div>
	);
}
