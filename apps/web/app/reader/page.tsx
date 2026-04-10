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
		<main className="mx-auto flex w-full max-w-7xl flex-col gap-10 px-4 py-8 md:px-6">
			<section className="grid gap-6 lg:grid-cols-[minmax(0,1.55fr)_minmax(320px,0.95fr)]">
				<Card className="border-border/70 shadow-sm">
					<CardHeader className="space-y-4">
						<Badge variant="outline" className="w-fit">
							Reader frontstage
						</Badge>
						<div className="space-y-3">
							<h1
								data-route-heading
								className="text-3xl font-semibold md:text-4xl"
							>
								Start with a finished reading unit
							</h1>
							<CardDescription className="max-w-3xl text-base leading-7">
								Open the strongest published document first, use the brief to
								orient yourself, and only leave the reader when you need more
								intake or trend context. This page is the frontstage for
								reading, not the operator control panel.
							</CardDescription>
						</div>
					</CardHeader>
					<CardContent className="space-y-6">
						<div className="flex flex-wrap gap-3">
							<Button asChild size="lg">
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
								</Link>
							</Button>
						</div>
						<p className="text-sm text-muted-foreground">
							Need a different surface?{" "}
							<Link className="underline underline-offset-4" href="/briefings">
								Briefings
							</Link>{" "}
							for the story-first summary,{" "}
							<Link className="underline underline-offset-4" href="/trends">
								Trends
							</Link>{" "}
							for repeated themes, or{" "}
							<Link
								className="underline underline-offset-4"
								href="/subscriptions"
							>
								Source intake
							</Link>{" "}
							when you need to add more material.
						</p>
						{leadDocument ? (
							<div className="rounded-2xl border border-border/70 bg-muted/20 p-6">
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
										<Badge variant="outline">{leadDocument.topic_label}</Badge>
									) : null}
								</div>
								<div className="mt-5 space-y-4">
									<div className="space-y-3">
										<CardTitle className="text-3xl leading-tight tracking-tight md:text-4xl">
											{leadDocument.title}
										</CardTitle>
										<p className="max-w-3xl text-base leading-7 text-muted-foreground">
											{leadDocument.summary ??
												"Open the current lead document to inspect the merged markdown, warning state, and source contribution ledger in one place."}
										</p>
										<p className="text-sm text-muted-foreground">
											Read the body first. Open source contribution only when
											you want to inspect provenance or warning detail.
										</p>
									</div>
									<div className="flex flex-wrap gap-2 text-sm text-muted-foreground">
										<span>Window {leadDocument.window_id}</span>
										<span>Version {leadDocument.version}</span>
										<span>Sources {leadDocument.source_item_count}</span>
									</div>
									{leadSources.length ? (
										<div className="rounded-2xl border border-border/60 bg-background/90 p-4">
											<p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
												Evidence sources
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
									<div className="flex flex-wrap gap-3">
										<Button asChild variant="outline">
											<Link href="/search">Search evidence</Link>
										</Button>
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
							</div>
						)}
					</CardContent>
				</Card>

				<Card className="border-border/70 shadow-sm lg:sticky lg:top-6">
					<CardHeader>
						<CardTitle className="text-xl">30-second brief</CardTitle>
						<CardDescription>
							A compact route map over the current published-doc layer. Use it
							to orient yourself, then return to the library or open the lead
							document.
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
											className="block rounded-xl border border-border/60 p-3 transition hover:bg-muted/40"
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
						<h2 className="text-2xl font-semibold tracking-tight">
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
							<Card key={document.id} className="border-amber-300/70 shadow-sm">
								<CardHeader className="space-y-3">
									<div className="flex flex-wrap items-center gap-2">
										<Badge variant="destructive">Yellow warning</Badge>
										{document.topic_label ? (
											<Badge variant="outline">{document.topic_label}</Badge>
										) : null}
									</div>
									<div>
										<CardTitle className="text-xl leading-7">
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
						<h2 className="text-2xl font-semibold tracking-tight">
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
							<Card key={document.id} className="border-border/70 shadow-sm">
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
									<div>
										<CardTitle className="text-xl leading-7">
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
		</main>
	);
}
