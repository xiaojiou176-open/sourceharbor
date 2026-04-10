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
							<CardTitle data-route-heading className="text-3xl md:text-4xl">
								Published reader documents
							</CardTitle>
							<CardDescription className="max-w-3xl text-base leading-7">
								A calmer reading deck for the current published-doc layer.
								Merged stories and singleton polish docs now share one editorial
								surface, while yellow-warning documents stay honest about
								missing or degraded source evidence.
							</CardDescription>
						</div>
					</CardHeader>
					<CardContent className="space-y-6">
						<div className="flex flex-wrap gap-3">
							<Button asChild>
								<Link href="/subscriptions">Open source intake</Link>
							</Button>
							<Button asChild variant="secondary">
								<Link href="/trends">Open trends</Link>
							</Button>
							<Button asChild variant="outline">
								<Link href="/briefings">Open briefings</Link>
							</Button>
						</div>
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
									</div>
									<div className="flex flex-wrap gap-2 text-sm text-muted-foreground">
										<span>Window {leadDocument.window_id}</span>
										<span>Version {leadDocument.version}</span>
										<span>Sources {leadDocument.source_item_count}</span>
									</div>
									{leadSources.length ? (
										<div className="grid gap-3 md:grid-cols-3">
											{leadSources.map((source) => (
												<div
													key={String(source.source_item_id ?? source.title)}
													className="rounded-xl border border-border/60 bg-background/90 p-3"
												>
													<p className="text-sm font-medium">
														{typeof source.title === "string" &&
														source.title.trim()
															? source.title
															: "Untitled source"}
													</p>
													{typeof source.digest_preview === "string" ? (
														<p className="mt-2 line-clamp-3 text-sm text-muted-foreground">
															{source.digest_preview}
														</p>
													) : null}
												</div>
											))}
										</div>
									) : null}
									<div className="flex flex-wrap gap-3">
										<Button asChild size="lg">
											<Link href={`/reader/${leadDocument.id}`}>
												Open reader detail
											</Link>
										</Button>
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
						<CardTitle className="text-xl">Navigation brief</CardTitle>
						<CardDescription>
							The 30-second guide over the current published-doc layer. Read the
							brief first, then drop into the document that matters most.
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
												<p className="mt-1 text-muted-foreground">
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
									<div className="space-y-2">
										{(Array.isArray(document.source_refs)
											? document.source_refs
											: []
										)
											.slice(0, 2)
											.map((source) => (
												<div
													key={String(source.source_item_id ?? source.title)}
													className="rounded-xl border border-border/60 bg-background/90 p-3 text-sm"
												>
													<p className="font-medium">
														{typeof source.title === "string" &&
														source.title.trim()
															? source.title
															: "Untitled source"}
													</p>
													{typeof source.digest_preview === "string" ? (
														<p className="mt-2 line-clamp-2 text-muted-foreground">
															{source.digest_preview}
														</p>
													) : null}
												</div>
											))}
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
