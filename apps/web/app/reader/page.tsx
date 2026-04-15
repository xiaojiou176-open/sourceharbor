import { ArrowRight, LibraryBig } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { SourceIdentityCard } from "@/components/source-identity-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { apiClient } from "@/lib/api/client";
import { editorialSans, editorialSerif } from "@/lib/editorial-fonts";
import { DEMO_READER_DOCUMENT_ID } from "@/lib/reader/demo-document";
import { buildProductMetadata } from "@/lib/seo";
import { resolveReaderSourceIdentity } from "@/lib/source-identity";

export const metadata: Metadata = buildProductMetadata({
	title: "Reader",
	description:
		"Finished SourceHarbor stories, reading shelf guidance, and source-aware reading flow.",
	route: "reader",
});

export default async function ReaderPage() {
	const [documentsResult, briefResult] = await Promise.all([
		apiClient
			.listPublishedReaderDocuments({ limit: 12 })
			.then((data) => ({ data, error: false }))
			.catch(() => ({ data: [], error: true })),
		apiClient
			.getNavigationBrief({ limit: 8 })
			.then((data) => ({ data, error: false }))
			.catch(() => ({ data: null, error: true })),
	]);

	const documents = documentsResult.data;
	const navigationBrief = briefResult.data;
	const documentsUnavailable = documentsResult.error;
	const briefUnavailable = briefResult.error;
	const navigationItems =
		navigationBrief && Array.isArray(navigationBrief.items)
			? navigationBrief.items
			: [];

	const clearDocuments = documents.filter(
		(document) => !document.published_with_gap,
	);
	const leadDocument = clearDocuments[0] ?? documents[0] ?? null;
	const totalDocuments = documents.length;
	const warningCount = documents.filter(
		(document) => document.published_with_gap,
	).length;
	const shelfUnavailable = documentsUnavailable && totalDocuments === 0;
	const leadSources =
		leadDocument && Array.isArray(leadDocument.source_refs)
			? leadDocument.source_refs.slice(0, 3)
			: [];
	const needsAttentionDocuments = documents.filter(
		(document) =>
			document.published_with_gap && document.id !== (leadDocument?.id ?? ""),
	);
	const libraryDocuments = documents.filter(
		(document) =>
			document.id !== (leadDocument?.id ?? "") && !document.published_with_gap,
	);
	const shelfSnapshotItems = shelfUnavailable
		? []
		: [
				{
					label: "Published",
					value: totalDocuments,
					valueLabel: String(totalDocuments),
				},
				{
					label: "Clear",
					value: clearDocuments.length,
					max: Math.max(totalDocuments, 1),
					valueLabel: String(clearDocuments.length),
					tone: "success" as const,
				},
				{
					label: "Warnings",
					value: warningCount,
					max: Math.max(totalDocuments, 1),
					valueLabel: String(warningCount),
					tone: warningCount > 0 ? ("warning" as const) : ("muted" as const),
				},
			];

	return (
		<div
			className={`mx-auto flex w-full max-w-7xl flex-col gap-14 px-4 py-8 md:px-6 ${editorialSans.className}`}
		>
			<section className="grid gap-6 xl:grid-cols-[minmax(0,1.52fr)_minmax(280px,0.72fr)]">
				<Card className="overflow-hidden border-border/70 bg-gradient-to-br from-background via-background to-rose-50/60 shadow-sm dark:to-rose-950/10">
					<CardHeader className="space-y-7 pb-4">
						<Badge
							variant="outline"
							className="w-fit border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/30 dark:text-rose-200"
						>
							{shelfUnavailable
								? "Reader temporarily unavailable"
								: "Reading shelf"}
						</Badge>
						<div className="space-y-4">
							<p className="text-xs font-semibold uppercase tracking-[0.28em] text-muted-foreground">
								{shelfUnavailable ? "Shelf status" : "Start here"}
							</p>
							<h1
								data-route-heading
								tabIndex={-1}
								className={`max-w-4xl text-4xl leading-[0.96] tracking-tight md:text-6xl xl:text-7xl ${editorialSerif.className}`}
							>
								{shelfUnavailable
									? "Reader shelf is temporarily unavailable"
									: "Pick a finished story and start reading"}
							</h1>
							<CardDescription className="max-w-3xl text-base leading-8 text-foreground/75">
								{shelfUnavailable
									? "The reading shelf could not be loaded just now. You can still open the sample story or check the backstage status while it recovers."
									: "Start with one finished story. Notes and source links are there when you need them, but the story should do the first job."}
							</CardDescription>
						</div>
					</CardHeader>
					<CardContent className="space-y-8 pb-8">
						<div className="flex flex-wrap items-center gap-3">
							{shelfUnavailable ? (
								<>
									<Button asChild size="lg" className="gap-2">
										<Link href={`/reader/${DEMO_READER_DOCUMENT_ID}`}>
											Open specimen detail
											<ArrowRight className="h-4 w-4" />
										</Link>
									</Button>
									<Button asChild variant="outline">
										<Link href="/ops">Open ops desk</Link>
									</Button>
								</>
							) : (
								<Button asChild size="lg" className="gap-2">
									<Link
										href={
											leadDocument
												? `/reader/${leadDocument.id}`
												: `/reader/${DEMO_READER_DOCUMENT_ID}`
										}
									>
										{leadDocument ? "Continue reading" : "Open specimen detail"}
										<ArrowRight className="h-4 w-4" />
									</Link>
								</Button>
							)}
						</div>
						{shelfSnapshotItems.length ? (
							<div className="flex flex-wrap gap-2 text-sm text-muted-foreground">
								{shelfSnapshotItems.map((item) => (
									<Badge key={item.label} variant="outline">
										{item.label}: {item.valueLabel}
									</Badge>
								))}
							</div>
						) : (
							<div className="rounded-[1.5rem] border border-border/60 bg-background/75 p-5 text-sm leading-7 text-foreground/75">
								This page is in fail-close mode. Open the sample story or the
								backstage status page, then come back once the live shelf
								recovers.
							</div>
						)}
						{leadDocument ? (
							<div className="grid gap-6 rounded-[1.75rem] border border-border/70 bg-background/80 p-6 xl:grid-cols-[minmax(0,1.22fr)_minmax(260px,0.72fr)]">
								<div className="space-y-5">
									<div className="flex flex-wrap items-center gap-2">
										<Badge variant="secondary">Featured story</Badge>
										<Badge
											variant={
												leadDocument.published_with_gap
													? "destructive"
													: "outline"
											}
										>
											{leadDocument.published_with_gap
												? "Read with care"
												: "Ready"}
										</Badge>
										{leadDocument.topic_label ? (
											<Badge variant="outline">
												{leadDocument.topic_label}
											</Badge>
										) : null}
									</div>
									<div className="space-y-3">
										<p className="text-xs font-semibold uppercase tracking-[0.26em] text-muted-foreground">
											Start here
										</p>
										<CardTitle className="font-serif text-4xl leading-[1.02] tracking-tight md:text-5xl">
											{leadDocument.title}
										</CardTitle>
										<p className="max-w-3xl text-base leading-8 text-foreground/75">
											{leadDocument.summary ??
												"Open this story to read the finished piece first, then open source notes only if you want to look closer."}
										</p>
									</div>
									<dl className="grid gap-3 text-sm text-muted-foreground sm:grid-cols-3">
										<div className="rounded-2xl border border-border/60 bg-muted/15 p-3">
											<dt className="text-xs font-semibold uppercase tracking-[0.18em]">
												Edition
											</dt>
											<dd className="mt-2 text-foreground/85">
												{leadDocument.window_id}
											</dd>
										</div>
										<div className="rounded-2xl border border-border/60 bg-muted/15 p-3">
											<dt className="text-xs font-semibold uppercase tracking-[0.18em]">
												Revision
											</dt>
											<dd className="mt-2 text-foreground/85">
												{leadDocument.version}
											</dd>
										</div>
										<div className="rounded-2xl border border-border/60 bg-muted/15 p-3">
											<dt className="text-xs font-semibold uppercase tracking-[0.18em]">
												Sources used
											</dt>
											<dd className="mt-2 text-foreground/85">
												{leadDocument.source_item_count}
											</dd>
										</div>
									</dl>
								</div>
								<aside className="space-y-4 rounded-3xl border border-border/60 bg-muted/20 p-5">
									<div className="flex items-center gap-2 text-sm font-medium text-foreground">
										<LibraryBig className="h-4 w-4 text-rose-600" />
										Reading note
									</div>
									<p className="text-sm leading-6 text-muted-foreground">
										Read the story first. Notes and source links stay close, but
										they should never be louder than the story itself.
									</p>
									{leadSources.length ? (
										<div className="rounded-2xl border border-border/60 bg-background/90 p-4">
											<p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
												Sources behind this story
											</p>
											<div className="mt-3 space-y-2 text-sm text-muted-foreground">
												{leadSources.map((source, index) => (
													<SourceIdentityCard
														key={String(source.source_item_id ?? source.title)}
														identity={{
															...resolveReaderSourceIdentity(source),
															eyebrow: `Footnote ${String(index + 1).padStart(2, "0")}`,
														}}
														compact
													/>
												))}
											</div>
										</div>
									) : null}
									<div className="space-y-2 text-sm text-muted-foreground">
										<p className="font-medium text-foreground">Keep going</p>
										<ul className="space-y-2">
											<li>
												<Link
													className="underline underline-offset-4"
													href="/briefings"
												>
													Briefings
												</Link>{" "}
												for the story-first sweep.
											</li>
											<li>
												<Link
													className="underline underline-offset-4"
													href="/trends"
												>
													Trends
												</Link>{" "}
												for repeated themes.
											</li>
											<li>
												<Link
													className="underline underline-offset-4"
													href="/subscriptions"
												>
													Add sources
												</Link>{" "}
												when the shelf needs more material.
											</li>
										</ul>
									</div>
								</aside>
							</div>
						) : (
							<div className="grid gap-4 rounded-[1.75rem] border border-dashed border-border/70 bg-muted/20 p-6 md:grid-cols-[minmax(0,1.3fr)_minmax(260px,0.8fr)]">
								<div>
									<p className="text-sm uppercase tracking-[0.24em] text-muted-foreground">
										Lead reading deck
									</p>
									<p className="mt-3 max-w-2xl text-base leading-7 text-muted-foreground">
										Bring in one source, let the first story finish, then come
										back here for the reading view.
									</p>
									<p className="mt-3 text-sm text-muted-foreground">
										Until the first live story lands, the sample story shows the
										same reading rhythm without pretending there is already real
										shelf content.
									</p>
								</div>
								<div className="rounded-2xl border border-border/60 bg-background/90 p-5">
									<p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">
										Showroom specimen
									</p>
									<p className="mt-3 text-sm leading-6 text-muted-foreground">
										Open one sample story first, then come back once the live
										shelf has materialized.
									</p>
									<Button asChild variant="outline" className="mt-4 w-full">
										<Link href={`/reader/${DEMO_READER_DOCUMENT_ID}`}>
											Open specimen detail
										</Link>
									</Button>
								</div>
							</div>
						)}
					</CardContent>
				</Card>

				<Card className="border-border/70 bg-background/95 shadow-sm lg:sticky lg:top-6">
					<CardHeader className="space-y-4">
						<Badge variant="outline" className="w-fit">
							Reading note
						</Badge>
							<p className="text-xs font-semibold uppercase tracking-[0.26em] text-muted-foreground">
								Up next
							</p>
							<h2 className="font-serif text-2xl font-semibold leading-none tracking-tight">
								Where to go next
							</h2>
							<CardDescription>
								Use this only when you want your next reading path. The story
								should still come first.
							</CardDescription>
					</CardHeader>
					<CardContent className="space-y-4 text-sm">
						{navigationBrief ? (
							<>
								<p className="text-muted-foreground">
									{navigationBrief.summary}
								</p>
								<div className="flex flex-wrap gap-2">
									<Badge variant="secondary">
										Stories {navigationBrief.document_count}
									</Badge>
									<Badge variant="outline">
										Needs note {navigationBrief.published_with_gap_count}
									</Badge>
								</div>
								<div className="space-y-2">
									{navigationItems.map((item, index) => (
										<Link
											key={item.document_id}
											href={item.route}
											className="block rounded-2xl border border-border/60 bg-muted/10 p-4 transition hover:border-rose-200/80 hover:bg-muted/30"
										>
											<div className="flex items-start gap-3">
												<span className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-border/60 text-xs font-semibold text-muted-foreground">
													{String(index + 1).padStart(2, "0")}
												</span>
												<div className="min-w-0">
													<p className="font-medium">{item.title}</p>
													{item.summary ? (
														<p className="mt-1 line-clamp-2 text-muted-foreground">
															{item.summary}
														</p>
													) : null}
												</div>
											</div>
										</Link>
									))}
								</div>
							</>
						) : (
							<div
								className="space-y-3"
								role={briefUnavailable ? "status" : undefined}
								aria-live={briefUnavailable ? "polite" : undefined}
								aria-atomic={briefUnavailable ? "true" : undefined}
							>
								<p className="text-muted-foreground">
									{briefUnavailable
										? "The quick guide is temporarily unavailable. Open the featured story or the sample story directly while it reloads."
										: "There is no guide yet. Until the first live story lands, use the sample story as your reading path."}
								</p>
								<div className="space-y-2">
									<div className="rounded-2xl border border-border/60 p-4">
										<p className="font-medium">01 Open the sample story</p>
										<p className="mt-1 text-muted-foreground">
											Read one finished sample before you worry about anything
											else.
										</p>
									</div>
									<div className="rounded-2xl border border-border/60 p-4">
										<p className="font-medium">
											02 Come back when the first live story lands
										</p>
										<p className="mt-1 text-muted-foreground">
											Once the first story is published, this guide turns into a
											short reading map.
										</p>
									</div>
								</div>
							</div>
						)}
					</CardContent>
				</Card>
			</section>

			{needsAttentionDocuments.length ? (
				<section className="space-y-4">
					<div className="space-y-2">
						<h2 className="font-serif text-3xl tracking-tight">
							Stories with notes
						</h2>
						<p className="text-sm text-muted-foreground">
							These stories are still readable. Open them when you want the
							latest piece and its note in view.
						</p>
					</div>
					<div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
						{needsAttentionDocuments.map((document) => (
							<Card
								key={document.id}
								className="border-amber-300/70 bg-amber-50/40 shadow-sm dark:bg-amber-950/10"
							>
								<CardHeader className="space-y-3">
									<div className="flex flex-wrap items-center gap-2">
										<Badge variant="destructive">Read with care</Badge>
										{document.topic_label ? (
											<Badge variant="outline">{document.topic_label}</Badge>
										) : null}
									</div>
									<div className="space-y-2">
										<p className="text-xs font-semibold uppercase tracking-[0.26em] text-amber-800/80 dark:text-amber-200/80">
											Read with caution
										</p>
										<CardTitle className="font-serif text-2xl leading-7">
											{document.title}
										</CardTitle>
										<CardDescription className="mt-2 leading-6">
											{document.summary ??
												"Readable now, with one note to keep nearby while you read."}
										</CardDescription>
									</div>
								</CardHeader>
								<CardContent className="space-y-4">
									<div className="flex flex-wrap gap-2 text-sm text-muted-foreground">
										<span>Edition {document.window_id}</span>
										<span>Revision {document.version}</span>
										<span>Sources used {document.source_item_count}</span>
									</div>
									<Button asChild className="w-full">
										<Link href={`/reader/${document.id}`}>
											Open story
										</Link>
									</Button>
								</CardContent>
							</Card>
						))}
					</div>
				</section>
			) : null}

			<section className="space-y-4">
				<div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
					<div>
						<h2 className="font-serif text-3xl tracking-tight">
							Reader library
						</h2>
						<p className="text-sm text-muted-foreground">
							Every card below is already a finished story you can read
							end-to-end.
						</p>
					</div>
					<p className="text-sm text-muted-foreground">
						Showing {libraryDocuments.length || (leadDocument ? 1 : 0)} document
						{libraryDocuments.length || !leadDocument ? "s" : ""}
					</p>
				</div>
				{libraryDocuments.length ? (
					<div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
						{libraryDocuments.map((document) => (
							<Card
								key={document.id}
								className="border-border/70 bg-background/95 shadow-sm"
							>
								<CardHeader className="space-y-3">
									<div className="flex flex-wrap items-center gap-2">
										<Badge variant="secondary">
											{document.materialization_mode}
										</Badge>
										<Badge variant="outline">Clear</Badge>
										{document.topic_label ? (
											<Badge variant="outline">{document.topic_label}</Badge>
										) : null}
									</div>
									<div className="space-y-2">
										<p className="text-xs font-semibold uppercase tracking-[0.26em] text-muted-foreground">
											Finished story
										</p>
										<CardTitle className="font-serif text-2xl leading-7">
											{document.title}
										</CardTitle>
										<CardDescription className="mt-2 leading-6">
											{document.summary ??
												"Open the story to read it cleanly, then open notes only if you want more context."}
										</CardDescription>
									</div>
								</CardHeader>
								<CardContent className="space-y-4">
									<div className="flex flex-wrap gap-2 text-sm text-muted-foreground">
										<span>Edition {document.window_id}</span>
										<span>Revision {document.version}</span>
										<span>Sources used {document.source_item_count}</span>
									</div>
									<p className="text-sm text-muted-foreground">
										Built from {document.source_item_count} source
										{document.source_item_count === 1 ? "" : "s"} and ready to
										read as one finished story.
									</p>
									<Button asChild className="w-full">
										<Link href={`/reader/${document.id}`}>
											Open story
										</Link>
									</Button>
								</CardContent>
							</Card>
						))}
					</div>
				) : leadDocument ? (
					<Card className="border-border/70 shadow-sm">
						<CardHeader>
							<CardTitle>You are caught up</CardTitle>
							<CardDescription>
								The current lead document is already carrying the reading load.
								New clear documents will appear here after the next batch lands.
							</CardDescription>
						</CardHeader>
					</Card>
				) : documentsUnavailable ? (
					<Card
						className="border-destructive/40 bg-destructive/5 shadow-sm"
						role="alert"
						aria-live="assertive"
						aria-atomic="true"
					>
						<CardHeader className="space-y-3">
							<CardTitle>Reader shelf is temporarily unavailable</CardTitle>
							<CardDescription>
								The published-document list could not be loaded just now. Open
								the specimen detail or the ops desk while the shelf recovers.
							</CardDescription>
						</CardHeader>
						<CardContent className="flex flex-wrap gap-3 pt-0">
							<Button asChild variant="outline">
								<Link href={`/reader/${DEMO_READER_DOCUMENT_ID}`}>
									Open specimen detail
								</Link>
							</Button>
							<Button asChild variant="outline">
								<Link href="/ops">Open ops desk</Link>
							</Button>
						</CardContent>
					</Card>
				) : (
					<Card className="border-border/70 shadow-sm">
						<CardHeader>
							<CardTitle>No finished stories yet</CardTitle>
							<CardDescription>
								Process one source, let the first story finish, then come back
								here for the reading shelf.
							</CardDescription>
						</CardHeader>
					</Card>
				)}
			</section>
		</div>
	);
}
