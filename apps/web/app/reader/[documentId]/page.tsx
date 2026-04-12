import { BookOpenText, FileStack, ListTree, NotebookText } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { MarkdownPreview } from "@/components/markdown-preview";
import { SourceContributionDrawer } from "@/components/source-contribution-drawer";
import { SourceIdentityCard } from "@/components/source-identity-card";
import { Badge } from "@/components/ui/badge";
import { Card, CardDescription, CardHeader } from "@/components/ui/card";
import { YellowWarningCard } from "@/components/yellow-warning-card";
import { apiClient } from "@/lib/api/client";
import { editorialSans, editorialSerif } from "@/lib/editorial-fonts";
import {
	buildDemoReaderDocument,
	DEMO_READER_DOCUMENT_ID,
} from "@/lib/reader/demo-document";
import { buildProductMetadata } from "@/lib/seo";
import { resolveReaderSourceIdentity } from "@/lib/source-identity";

type ReaderDetailPageProps = {
	params: Promise<{ documentId: string }> | { documentId: string };
};

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
			? "Preview the reader detail frontstage with warning and evidence drawer before your first live document lands."
			: "Published reader document detail with markdown body, yellow warning state, and source contribution drawer.",
		route: "reader",
	});
}

export default async function ReaderDetailPage({
	params,
}: ReaderDetailPageProps) {
	const resolved = await params;
	const document =
		resolved.documentId === DEMO_READER_DOCUMENT_ID
			? buildDemoReaderDocument()
			: await apiClient
					.getPublishedReaderDocument(resolved.documentId)
					.catch(() => null);

	if (!document) {
		notFound();
	}

	const coverageLedger =
		document.coverage_ledger && typeof document.coverage_ledger === "object"
			? document.coverage_ledger
			: {};
	const sections = Array.isArray(document.sections) ? document.sections : [];
	const topSources = Array.isArray(document.source_refs)
		? document.source_refs.slice(0, 2)
		: [];
	const warningReasons = Array.isArray(document.warning?.reasons)
		? document.warning.reasons
		: [];

	return (
		<div
			className={`mx-auto flex w-full max-w-6xl flex-col gap-12 px-4 py-8 md:px-6 ${editorialSans.className}`}
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
					<span>Reader frontstage</span>
					<span>/</span>
					<span>{document.topic_label ?? "Published document"}</span>
				</div>
				<div className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(260px,0.78fr)]">
					<div className="space-y-4">
						<div className="flex flex-wrap items-center gap-2">
							<Badge variant="secondary">{document.materialization_mode}</Badge>
							{resolved.documentId === DEMO_READER_DOCUMENT_ID ? (
								<Badge variant="outline">Preview sample</Badge>
							) : null}
							<Badge
								variant={
									document.published_with_gap ? "destructive" : "outline"
								}
							>
								{document.published_with_gap ? "Yellow warning" : "Clear"}
							</Badge>
							{document.topic_label ? (
								<Badge variant="outline">{document.topic_label}</Badge>
							) : null}
						</div>
						<p className="text-xs font-semibold uppercase tracking-[0.28em] text-foreground/70">
							Published reading unit
						</p>
						<h1
							data-route-heading
							tabIndex={-1}
							className={`max-w-4xl text-4xl leading-[0.98] tracking-tight md:text-5xl xl:text-6xl ${editorialSerif.className}`}
						>
							{document.title}
						</h1>
						<p className="max-w-4xl text-base leading-8 text-foreground/75">
							{document.summary ??
								"This document unifies the reader-facing markdown, yellow-warning contract, and source contribution drawer for one published reader unit."}
						</p>
						{topSources.length ? (
							<div className="space-y-3">
								<p className="text-xs font-semibold uppercase tracking-[0.24em] text-muted-foreground">
									Source universe
								</p>
								<div className="grid gap-3 md:grid-cols-2">
									{topSources.map((source, index) => (
										<SourceIdentityCard
											key={String(source.source_item_id ?? index)}
											identity={{
												...resolveReaderSourceIdentity(source),
												eyebrow: `Primary source ${String(index + 1).padStart(2, "0")}`,
											}}
											compact
										/>
									))}
								</div>
							</div>
						) : null}
						{resolved.documentId === DEMO_READER_DOCUMENT_ID ? (
							<div className="max-w-3xl rounded-2xl border border-rose-200/70 bg-rose-50/70 p-4 text-sm leading-6 text-rose-950/80 dark:border-rose-900/60 dark:bg-rose-950/20 dark:text-rose-100/80">
								This is a specimen edition: read the body first, keep the
								warning in mind, then open evidence only when you want to
								inspect the backstage contract.
							</div>
						) : null}
						<div className="flex flex-wrap gap-3 text-sm text-foreground/75">
							<span>Window {document.window_id}</span>
							<span>Version {document.version}</span>
							<span>Sources {document.source_item_count}</span>
						</div>
						<div className="flex flex-wrap gap-2 text-sm">
							<a
								href="#reader-body"
								className="rounded-full border border-border/60 px-3 py-1 text-foreground/80 no-underline transition hover:bg-muted/40"
							>
								Read the body
							</a>
							<a
								href="#reader-warning"
								className="rounded-full border border-border/60 px-3 py-1 text-foreground/80 no-underline transition hover:bg-muted/40"
							>
								Keep the warning in mind
							</a>
							<a
								href="#reader-evidence"
								className="rounded-full border border-border/60 px-3 py-1 text-foreground/80 no-underline transition hover:bg-muted/40"
							>
								Open evidence when needed
							</a>
							<a
								href="#reader-coverage"
								className="rounded-full border border-border/60 px-3 py-1 text-foreground/80 no-underline transition hover:bg-muted/40"
							>
								Check coverage last
							</a>
						</div>
					</div>
					<aside className="rounded-3xl border border-border/70 bg-gradient-to-br from-background via-background to-rose-50/60 p-5 shadow-sm dark:to-rose-950/10">
						<div className="flex items-center gap-2 text-sm font-medium text-foreground">
							<BookOpenText className="h-4 w-4 text-rose-600" />
							Margin note
						</div>
						<p className="mt-2 text-sm leading-6 text-muted-foreground">
							This rail is here to keep your place, not to compete with the main
							narrative. Read the body like a finished article, then step into
							warning, footnotes, and coverage in that order.
						</p>
						<ol className="mt-4 space-y-3 text-sm">
							<li className="rounded-2xl border border-border/60 bg-background/85 p-4">
								<p className="text-xs font-semibold uppercase tracking-[0.24em] text-muted-foreground">
									01 Body pass
								</p>
								<p className="mt-2 leading-6 text-muted-foreground">
									Read the finished markdown as one deck before touching the
									backstage tools.
								</p>
							</li>
							<li className="rounded-2xl border border-border/60 bg-background/85 p-4">
								<p className="text-xs font-semibold uppercase tracking-[0.24em] text-muted-foreground">
									02 Warning pass
								</p>
								<p className="mt-2 leading-6 text-muted-foreground">
									Keep the caution in view, but do not let it replace the main
									argument.
								</p>
							</li>
							<li className="rounded-2xl border border-border/60 bg-background/85 p-4">
								<p className="text-xs font-semibold uppercase tracking-[0.24em] text-muted-foreground">
									03 Footnote pass
								</p>
								<p className="mt-2 leading-6 text-muted-foreground">
									Open evidence only when you need provenance, then check
									coverage last.
								</p>
							</li>
						</ol>
						{sections.length ? (
							<div className="mt-4 rounded-2xl border border-border/60 bg-background/85 p-4">
								<div className="flex items-center gap-2 text-sm font-medium text-foreground">
									<ListTree className="h-4 w-4 text-rose-600" />
									Section outline
								</div>
								<ul className="mt-3 space-y-2 text-sm text-muted-foreground">
									{sections.map((section) => (
										<li
											key={section.section_id}
											className="rounded-xl border border-border/50 px-3 py-2"
										>
											<p className="font-medium text-foreground">
												{section.title}
											</p>
											<p className="mt-1 text-xs">
												Linked source items: {section.source_item_ids.length}
											</p>
										</li>
									))}
								</ul>
							</div>
						) : null}
					</aside>
				</div>
			</section>

			<section id="reader-body" className="space-y-5">
				<div className="space-y-2">
					<div className="flex items-center gap-2 text-sm font-medium text-foreground">
						<NotebookText className="h-4 w-4 text-rose-600" />
						Reader body
					</div>
					<CardDescription className="max-w-3xl leading-6">
						The published markdown unit. Treat this as the frontstage and let it
						carry the first pass before you inspect supporting rails.
					</CardDescription>
					{sections.length ? (
						<div className="flex flex-wrap gap-2">
							{sections.map((section) => (
								<Badge key={section.section_id} variant="outline">
									{section.title}
								</Badge>
							))}
						</div>
					) : null}
				</div>
				<article className="rounded-[2rem] border border-border/70 bg-background/95 shadow-sm">
					<div className="mx-auto max-w-[74ch] p-5 md:p-8">
						<MarkdownPreview markdown={document.markdown} />
					</div>
				</article>
			</section>

			<section id="reader-warning">
				{document.published_with_gap ? (
					<YellowWarningCard reasons={warningReasons} />
				) : (
					<Card className="border-border/70 bg-muted/20 shadow-sm">
						<CardHeader className="space-y-3 pb-4">
							<div className="flex items-center gap-2 text-sm font-medium text-foreground">
								<FileStack className="h-4 w-4 text-rose-600" />
								Reading contract
							</div>
							<CardDescription className="leading-6">
								This document is published as a stable reading unit. Stay with
								the body as the main narrative, then step into evidence only if
								you need to inspect provenance or coverage detail.
							</CardDescription>
						</CardHeader>
					</Card>
				)}
			</section>

			<section id="reader-evidence">
				<SourceContributionDrawer document={document} />
			</section>

			<details
				id="reader-coverage"
				className="rounded-3xl border border-border/70 bg-muted/20 p-5 shadow-sm"
			>
				<summary className="cursor-pointer list-none">
					<span className="flex items-center gap-2 text-sm font-medium text-foreground">
						<FileStack className="h-4 w-4 text-rose-600" />
						Coverage snapshot
					</span>
					<p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
						Check coverage last, after the body, warning, and footnote drawer.
					</p>
				</summary>
				<div className="mt-4 grid gap-3 text-sm md:grid-cols-3">
					<div className="rounded-2xl border border-border/60 bg-background/85 p-4">
						<p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
							Covered sources
						</p>
						<p className="mt-2 text-lg font-semibold text-foreground">
							{String(
								(coverageLedger as { covered_source_count?: number })
									.covered_source_count ?? "n/a",
							)}
						</p>
					</div>
					<div className="rounded-2xl border border-border/60 bg-background/85 p-4">
						<p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
							Gap sources
						</p>
						<p className="mt-2 text-lg font-semibold text-foreground">
							{String(
								(coverageLedger as { gap_source_count?: number })
									.gap_source_count ?? "n/a",
							)}
						</p>
					</div>
					<div className="rounded-2xl border border-border/60 bg-background/85 p-4">
						<p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
							Ledger kind
						</p>
						<p className="mt-2 break-all text-sm text-foreground">
							{String(
								(coverageLedger as { ledger_kind?: string }).ledger_kind ??
									"unknown",
							)}
						</p>
					</div>
				</div>
			</details>
		</div>
	);
}
