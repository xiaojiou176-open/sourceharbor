import {
	ArrowRight,
	BookOpenText,
	LibraryBig,
	NotebookTabs,
	Search,
} from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

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
import { DEMO_READER_DOCUMENT_ID } from "@/lib/reader/demo-document";
import { buildProductMetadata } from "@/lib/seo";

export const metadata: Metadata = buildProductMetadata({
	title: "Reader",
	description:
		"Published reader documents, navigation brief, and yellow-warning surfaced reading flow for SourceHarbor.",
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

	return (
		<div className="mx-auto flex w-full max-w-7xl flex-col gap-12 px-4 py-8 md:px-6">
			<section className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.92fr)]">
				<Card className="overflow-hidden border-border/70 bg-gradient-to-br from-background via-background to-rose-50/60 shadow-sm dark:to-rose-950/10">
					<CardHeader className="space-y-6 pb-4">
						<Badge
							variant="outline"
							className="w-fit border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/30 dark:text-rose-200"
						>
							Reader frontstage
						</Badge>
						<div className="space-y-4">
							<p className="text-xs font-semibold uppercase tracking-[0.28em] text-muted-foreground">
								Published reading desk
							</p>
							<h1
								data-route-heading
								className="max-w-4xl font-serif text-4xl leading-[0.96] tracking-tight md:text-6xl xl:text-7xl"
							>
								Read the strongest finished unit before you touch the operator
								rails
							</h1>
							<CardDescription className="max-w-3xl text-base leading-8 text-foreground/75">
								Start where the story is already materialized. The lead deck
								gives you one clean reading unit, the brief keeps you oriented,
								and the rest of the library stays available without dragging you
								back into intake or dashboard mode.
							</CardDescription>
						</div>
						<div className="grid gap-3 md:grid-cols-3">
							<div className="rounded-2xl border border-border/60 bg-background/80 p-4">
								<div className="flex items-center gap-2 text-sm font-medium text-foreground">
									<BookOpenText className="h-4 w-4 text-rose-600" />
									Read body first
								</div>
								<p className="mt-2 text-sm leading-6 text-muted-foreground">
									Open the published document as a single unit instead of
									reconstructing the story from source fragments.
								</p>
							</div>
							<div className="rounded-2xl border border-border/60 bg-background/80 p-4">
								<div className="flex items-center gap-2 text-sm font-medium text-foreground">
									<NotebookTabs className="h-4 w-4 text-rose-600" />
									Keep context close
								</div>
								<p className="mt-2 text-sm leading-6 text-muted-foreground">
									Use the brief as a desk note, not as a second stage that
									steals attention from the reading unit.
								</p>
							</div>
							<div className="rounded-2xl border border-border/60 bg-background/80 p-4">
								<div className="flex items-center gap-2 text-sm font-medium text-foreground">
									<Search className="h-4 w-4 text-rose-600" />
									Verify on demand
								</div>
								<p className="mt-2 text-sm leading-6 text-muted-foreground">
									Only leave the page for search, trends, or intake when the
									current deck no longer answers the question you came with.
								</p>
							</div>
						</div>
					</CardHeader>
					<CardContent className="space-y-8 pb-8">
						<div className="flex flex-wrap items-center gap-3">
							<Button asChild size="lg" className="gap-2">
								<Link
									href={
										leadDocument
											? `/reader/${leadDocument.id}`
											: "/subscriptions"
									}
								>
									{leadDocument
										? "Continue reading"
										: "Create the first reader document"}
									<ArrowRight className="h-4 w-4" />
								</Link>
							</Button>
							{!leadDocument ? (
								<Button asChild variant="outline" size="lg">
									<Link href={`/reader/${DEMO_READER_DOCUMENT_ID}`}>
										Preview the detail view
									</Link>
								</Button>
							) : null}
							<div className="flex flex-wrap gap-2 text-sm text-muted-foreground">
								<Badge variant="secondary">Published {totalDocuments}</Badge>
								<Badge variant="outline">Clear {clearDocuments.length}</Badge>
								<Badge variant="outline">Warnings {warningCount}</Badge>
							</div>
						</div>
						{leadDocument ? (
							<div className="grid gap-6 rounded-[1.75rem] border border-border/70 bg-background/80 p-6 xl:grid-cols-[minmax(0,1.25fr)_minmax(280px,0.78fr)]">
								<div className="space-y-5">
									<div className="flex flex-wrap items-center gap-2">
										<Badge variant="secondary">Lead document</Badge>
										<Badge
											variant={
												leadDocument.published_with_gap
													? "destructive"
													: "outline"
											}
										>
											{leadDocument.published_with_gap
												? "Yellow warning"
												: "Clear"}
										</Badge>
										{leadDocument.topic_label ? (
											<Badge variant="outline">
												{leadDocument.topic_label}
											</Badge>
										) : null}
									</div>
									<div className="space-y-3">
										<p className="text-xs font-semibold uppercase tracking-[0.26em] text-muted-foreground">
											Today&apos;s strongest deck
										</p>
										<CardTitle className="font-serif text-4xl leading-[1.02] tracking-tight md:text-5xl">
											{leadDocument.title}
										</CardTitle>
										<p className="max-w-3xl text-base leading-8 text-foreground/75">
											{leadDocument.summary ??
												"Open the current lead document to inspect the merged markdown, warning state, and source contribution ledger in one place."}
										</p>
									</div>
									<div className="flex flex-wrap gap-2 text-sm text-muted-foreground">
										<span>Window {leadDocument.window_id}</span>
										<span>Version {leadDocument.version}</span>
										<span>Sources {leadDocument.source_item_count}</span>
									</div>
									<div className="flex flex-wrap gap-3">
										<Button asChild variant="outline" className="gap-2">
											<Link href="/search">
												Search evidence
												<ArrowRight className="h-4 w-4" />
											</Link>
										</Button>
									</div>
								</div>
								<div className="space-y-4 rounded-3xl border border-border/60 bg-muted/20 p-5">
									<div className="flex items-center gap-2 text-sm font-medium text-foreground">
										<LibraryBig className="h-4 w-4 text-rose-600" />
										Reading desk note
									</div>
									<p className="text-sm leading-6 text-muted-foreground">
										Stay with this deck until you hit a question the body cannot
										answer. The goal is fewer tabs, not more surface hopping.
									</p>
									{leadSources.length ? (
										<div className="rounded-2xl border border-border/60 bg-background/90 p-4">
											<p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
												First three evidence lanes
											</p>
											<ul className="mt-3 space-y-2 text-sm text-muted-foreground">
												{leadSources.map((source) => (
													<li
														key={String(source.source_item_id ?? source.title)}
														className="rounded-xl border border-border/50 px-3 py-2"
													>
														<p className="font-medium text-foreground">
															{typeof source.title === "string" &&
															source.title.trim()
																? source.title
																: "Untitled source"}
														</p>
														{typeof source.digest_preview === "string" ? (
															<p className="mt-1 line-clamp-2">
																{source.digest_preview}
															</p>
														) : null}
													</li>
												))}
											</ul>
										</div>
									) : null}
									<div className="space-y-2 text-sm text-muted-foreground">
										<p>Need another rail?</p>
										<p>
											<Link
												className="underline underline-offset-4"
												href="/briefings"
											>
												Briefings
											</Link>{" "}
											for the story-first sweep,{" "}
											<Link
												className="underline underline-offset-4"
												href="/trends"
											>
												Trends
											</Link>{" "}
											for repeated themes, or{" "}
											<Link
												className="underline underline-offset-4"
												href="/subscriptions"
											>
												Source intake
											</Link>{" "}
											when the shelf itself needs more material.
										</p>
									</div>
								</div>
							</div>
						) : (
							<div className="rounded-2xl border border-dashed border-border/70 bg-muted/20 p-6">
								<p className="text-sm uppercase tracking-[0.24em] text-muted-foreground">
									Lead reading deck
								</p>
								<p className="mt-3 max-w-2xl text-base leading-7 text-muted-foreground">
									Run intake, freeze a batch, and materialize the reader
									pipeline to turn raw source items into readable documents on
									this frontstage.
								</p>
								<p className="mt-3 text-sm text-muted-foreground">
									If you want to inspect the detail-state layout before the
									first live deck lands, open the preview detail view from the
									hero actions above.
								</p>
							</div>
						)}
					</CardContent>
				</Card>

				<Card className="border-border/70 bg-background/95 shadow-sm lg:sticky lg:top-6">
					<CardHeader>
						<p className="text-xs font-semibold uppercase tracking-[0.26em] text-muted-foreground">
							Orientation note
						</p>
						<h2 className="font-serif text-2xl font-semibold leading-none tracking-tight">
							30-second brief
						</h2>
						<CardDescription>
							A compact route map over the current published-doc layer. Read it
							like a margin note, then go back to the strongest deck.
						</CardDescription>
					</CardHeader>
					<CardContent className="space-y-3 text-sm">
						{navigationBrief ? (
							<>
								<p>{navigationBrief.summary}</p>
								<div className="flex flex-wrap gap-2">
									<Badge variant="secondary">
										Docs {navigationBrief.document_count}
									</Badge>
									<Badge variant="outline">
										Yellow warnings {navigationBrief.published_with_gap_count}
									</Badge>
								</div>
								<div className="space-y-2">
									{navigationItems.map((item) => (
										<Link
											key={item.document_id}
											href={item.route}
											className="block rounded-2xl border border-border/60 p-4 transition hover:bg-muted/40"
										>
											<p className="font-medium">{item.title}</p>
											{item.summary ? (
												<p className="mt-1 line-clamp-2 text-muted-foreground">
													{item.summary}
												</p>
											) : null}
										</Link>
									))}
								</div>
							</>
						) : (
							<p className="text-muted-foreground">
								No navigation brief is available yet. Materialize one
								consumption batch first.
							</p>
						)}
					</CardContent>
				</Card>
			</section>

			{needsAttentionDocuments.length ? (
				<section className="space-y-4">
					<div className="space-y-2">
						<h2 className="font-serif text-3xl tracking-tight">
							Needs attention
						</h2>
						<p className="text-sm text-muted-foreground">
							These documents stay readable, but they still carry yellow-warning
							disclosure. Open them when you want the latest story with an
							explicit caution label.
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
										<Badge variant="destructive">Yellow warning</Badge>
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
												"Readable now, but still carrying explicit warning disclosure."}
										</CardDescription>
									</div>
								</CardHeader>
								<CardContent className="space-y-4">
									<div className="flex flex-wrap gap-2 text-sm text-muted-foreground">
										<span>Window {document.window_id}</span>
										<span>Version {document.version}</span>
										<span>Sources {document.source_item_count}</span>
									</div>
									<Button asChild className="w-full">
										<Link href={`/reader/${document.id}`}>
											Open reader detail
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
							Every card below is already a published reader document, whether
							it came from a merge path or a singleton polish path.
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
											Published unit
										</p>
										<CardTitle className="font-serif text-2xl leading-7">
											{document.title}
										</CardTitle>
										<CardDescription className="mt-2 leading-6">
											{document.summary ??
												"Open the document to inspect the merged reader markdown and source contributions."}
										</CardDescription>
									</div>
								</CardHeader>
								<CardContent className="space-y-4">
									<div className="flex flex-wrap gap-2 text-sm text-muted-foreground">
										<span>Window {document.window_id}</span>
										<span>Version {document.version}</span>
										<span>Sources {document.source_item_count}</span>
									</div>
									<p className="text-sm text-muted-foreground">
										Backed by {document.source_item_count} source
										{document.source_item_count === 1 ? "" : "s"} and ready to
										open as one published reading unit.
									</p>
									<Button asChild className="w-full">
										<Link href={`/reader/${document.id}`}>
											Open reader detail
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
				) : (
					<Card className="border-border/70 shadow-sm">
						<CardHeader>
							<CardTitle>No published reader documents yet</CardTitle>
							<CardDescription>
								Run the intake path, freeze a consumption batch, then
								materialize the reader pipeline so this surface has real output
								to show.
							</CardDescription>
						</CardHeader>
					</Card>
				)}
			</section>
		</div>
	);
}
