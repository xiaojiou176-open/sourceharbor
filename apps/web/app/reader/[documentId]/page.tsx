import { FileStack, ListTree, NotebookText } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { getActionSessionTokenForForm } from "@/app/action-security";
import { MarkdownPreview } from "@/components/markdown-preview";
import { ReaderRepairPanel } from "@/components/reader-repair-panel";
import { SourceContributionDrawer } from "@/components/source-contribution-drawer";
import { SourceIdentityCard } from "@/components/source-identity-card";
import { Badge } from "@/components/ui/badge";
import { Card, CardDescription, CardHeader } from "@/components/ui/card";
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
	const isPreviewRoute = resolved.documentId === DEMO_READER_DOCUMENT_ID;
	const document = isPreviewRoute
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
	const traceabilityPack =
		document.traceability_pack && typeof document.traceability_pack === "object"
			? document.traceability_pack
			: {};
	const sections = Array.isArray(document.sections) ? document.sections : [];
	const topSources = Array.isArray(document.source_refs)
		? document.source_refs.slice(0, 2)
		: [];
	const warningReasons = Array.isArray(document.warning?.reasons)
		? document.warning.reasons
		: [];
	const repairHistory = Array.isArray(document.repair_history)
		? document.repair_history
		: [];
	const sessionToken = getActionSessionTokenForForm();
	const coverageStatus = String(
		(coverageLedger as { status?: string }).status ?? "unknown",
	);
	const traceabilityStatus = String(
		(traceabilityPack as { status?: string }).status ?? "unknown",
	);
	const traceabilitySections = Array.isArray(
		(traceabilityPack as { section_contributions?: unknown[] })
			.section_contributions,
	)
		? (
				traceabilityPack as {
					section_contributions: Array<Record<string, unknown>>;
				}
			).section_contributions
		: [];
	const traceabilitySources = Array.isArray(
		(traceabilityPack as { source_items?: unknown[] }).source_items,
	)
		? (traceabilityPack as { source_items: Array<Record<string, unknown>> })
				.source_items
		: [];
	const traceabilityAffectedSources = Array.isArray(
		(traceabilityPack as { affected_source_item_ids?: unknown[] })
			.affected_source_item_ids,
	)
		? (traceabilityPack as { affected_source_item_ids: Array<string | number> })
				.affected_source_item_ids
		: [];
	const evidenceRouteCount = Object.values(
		(traceabilityPack as { evidence_routes?: Record<string, unknown> })
			.evidence_routes ?? {},
	).reduce<number>((count, value) => {
		if (Array.isArray(value)) {
			return count + value.length;
		}
		return count;
	}, 0);

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
								variant="outline"
								className={
									document.published_with_gap
										? "border-amber-500/45 bg-amber-500/12 text-amber-800"
										: undefined
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
					<div className="rounded-3xl border border-border/70 bg-gradient-to-br from-background via-background to-rose-50/60 p-5 shadow-sm dark:to-rose-950/10">
						<p
							className={`text-[11px] uppercase tracking-[0.22em] text-muted-foreground ${editorialMono.className}`}
						>
							Margin note
						</p>
						<h2
							className={`mt-2 text-2xl leading-tight text-foreground ${editorialSerif.className}`}
						>
							Keep the article in front. Keep proof in the margin.
						</h2>
						<p className="mt-3 text-sm leading-6 text-muted-foreground">
							This rail is here to keep your place, not to compete with the main
							narrative. Read the body like a finished article, then step into
							warning, footnotes, and coverage in that order.
						</p>
						<ol className="mt-5 divide-y divide-border/60 border-y border-border/60 text-sm">
							<li className="grid gap-3 py-4 md:grid-cols-[88px_minmax(0,1fr)]">
								<p
									className={`text-[11px] uppercase tracking-[0.22em] text-muted-foreground ${editorialMono.className}`}
								>
									01 Body pass
								</p>
								<p className="leading-6 text-muted-foreground">
									Read the finished markdown as one deck before touching the
									backstage tools.
								</p>
							</li>
							<li className="grid gap-3 py-4 md:grid-cols-[88px_minmax(0,1fr)]">
								<p
									className={`text-[11px] uppercase tracking-[0.22em] text-muted-foreground ${editorialMono.className}`}
								>
									02 Warning pass
								</p>
								<p className="leading-6 text-muted-foreground">
									Keep the caution in view, but do not let it replace the main
									argument.
								</p>
							</li>
							<li className="grid gap-3 py-4 md:grid-cols-[88px_minmax(0,1fr)]">
								<p
									className={`text-[11px] uppercase tracking-[0.22em] text-muted-foreground ${editorialMono.className}`}
								>
									03 Footnotes
								</p>
								<p className="leading-6 text-muted-foreground">
									Open evidence only when you need provenance, then check
									coverage and repair last.
								</p>
							</li>
						</ol>
						{sections.length ? (
							<details className="mt-5 rounded-[1.35rem] border border-border/60 bg-background/82 p-4">
								<summary className="cursor-pointer list-none">
									<div className="flex items-center justify-between gap-3">
										<div>
											<p
												className={`text-[11px] uppercase tracking-[0.22em] text-muted-foreground ${editorialMono.className}`}
											>
												Section outline
											</p>
											<p className="mt-1 text-sm text-foreground">
												Open the map only when you need to re-anchor yourself.
											</p>
										</div>
										<ListTree className="h-4 w-4 text-rose-600" />
									</div>
								</summary>
								<ul className="mt-4 space-y-2 text-sm text-muted-foreground">
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
							</details>
						) : null}
					</div>
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

			<section id="reader-coverage" className="space-y-4">
				<div className="space-y-2">
					<p
						className={`text-[11px] uppercase tracking-[0.22em] text-muted-foreground ${editorialMono.className}`}
					>
						Margin proof rail
					</p>
					<h2
						className={`text-2xl leading-tight text-foreground ${editorialSerif.className}`}
					>
						Coverage, traceability, and repair stay beside the article.
					</h2>
					<p className="max-w-3xl text-sm leading-6 text-muted-foreground">
						These panels are here to verify what you just read, not to replace
						the reading flow with a second dashboard.
					</p>
				</div>

				<div className="grid gap-4 xl:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)]">
					<Card className="border-border/70 bg-muted/20 shadow-sm">
						<CardHeader className="space-y-3 pb-4">
							<div className="flex items-center gap-2 text-sm font-medium text-foreground">
								<FileStack className="h-4 w-4 text-rose-600" />
								Coverage snapshot
							</div>
							<CardDescription className="leading-6">
								Check coverage last, after the body, warning, and footnote
								drawer.
							</CardDescription>
						</CardHeader>
						<CardDescription className="px-6 pb-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">
							{coverageStatus}
						</CardDescription>
						<div className="px-6 pb-6">
							<dl className="grid gap-3 sm:grid-cols-2">
								<div className="rounded-2xl border border-border/60 bg-background/85 p-4">
									<dt className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
										Covered sources
									</dt>
									<dd className="mt-2 text-lg font-semibold text-foreground">
										{String(
											(coverageLedger as { covered_source_count?: number })
												.covered_source_count ?? "n/a",
										)}
									</dd>
								</div>
								<div className="rounded-2xl border border-border/60 bg-background/85 p-4">
									<dt className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
										Gap sources
									</dt>
									<dd className="mt-2 text-lg font-semibold text-foreground">
										{String(
											(coverageLedger as { gap_source_count?: number })
												.gap_source_count ?? "n/a",
										)}
									</dd>
								</div>
								<div className="rounded-2xl border border-border/60 bg-background/85 p-4 sm:col-span-2">
									<dt className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
										Ledger kind
									</dt>
									<dd className="mt-2 break-all text-sm text-foreground">
										{String(
											(coverageLedger as { ledger_kind?: string })
												.ledger_kind ?? "unknown",
										)}
									</dd>
								</div>
							</dl>
						</div>
					</Card>

					<Card className="border-border/70 bg-muted/20 shadow-sm">
						<CardHeader className="space-y-3 pb-4">
							<div className="flex items-center gap-2 text-sm font-medium text-foreground">
								<ListTree className="h-4 w-4 text-rose-600" />
								Traceability snapshot
							</div>
							<CardDescription className="leading-6">
								This is the proof rail behind the article: which sections are
								traced, how many source items are mapped, and how much evidence
								is ready to open on demand.
							</CardDescription>
						</CardHeader>
						<CardDescription className="px-6 pb-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">
							{traceabilityStatus}
						</CardDescription>
						<div className="px-6 pb-6">
							<dl className="grid gap-3 sm:grid-cols-2">
								<div className="rounded-2xl border border-border/60 bg-background/85 p-4">
									<dt className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
										Sections traced
									</dt>
									<dd className="mt-2 text-lg font-semibold text-foreground">
										{traceabilitySections.length}
									</dd>
								</div>
								<div className="rounded-2xl border border-border/60 bg-background/85 p-4">
									<dt className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
										Sources mapped
									</dt>
									<dd className="mt-2 text-lg font-semibold text-foreground">
										{traceabilitySources.length}
									</dd>
								</div>
								<div className="rounded-2xl border border-border/60 bg-background/85 p-4">
									<dt className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
										Affected sources
									</dt>
									<dd className="mt-2 text-lg font-semibold text-foreground">
										{traceabilityAffectedSources.length}
									</dd>
								</div>
								<div className="rounded-2xl border border-border/60 bg-background/85 p-4">
									<dt className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
										Evidence routes
									</dt>
									<dd className="mt-2 text-lg font-semibold text-foreground">
										{evidenceRouteCount}
									</dd>
								</div>
							</dl>
						</div>
					</Card>
				</div>

				{isPreviewRoute ? (
					<Card className="border-border/70 bg-background/95 shadow-sm">
						<CardHeader className="space-y-3 pb-4">
							<div className="flex items-center gap-2 text-sm font-medium text-foreground">
								<FileStack className="h-4 w-4 text-rose-600" />
								Repair preview
							</div>
							<CardDescription className="leading-6">
								This specimen shows where repair lives in the reading flow, but
								the buttons stay disabled until you open a real published reader
								document with a server-owned identifier.
							</CardDescription>
						</CardHeader>
						<div className="px-6 pb-6">
							<div className="rounded-2xl border border-border/60 bg-muted/15 p-4 text-sm leading-6 text-muted-foreground">
								Use this panel as a map, not as a live control surface. Open a
								real reader edition when you want patch, section, or cluster
								repair to run.
							</div>
						</div>
					</Card>
				) : (
					<ReaderRepairPanel
						documentId={document.id}
						publishedWithGap={document.published_with_gap}
						repairHistoryCount={repairHistory.length}
						sectionIds={sections.map((section) => section.section_id)}
						sessionToken={sessionToken}
					/>
				)}
			</section>
		</div>
	);
}
