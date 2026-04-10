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

	return (
		<main className="mx-auto flex w-full max-w-7xl flex-col gap-8 px-4 py-8 md:px-6">
			<section className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
				<Card className="border-border/70">
					<CardHeader>
						<Badge variant="outline" className="w-fit">
							Reader frontstage
						</Badge>
						<CardTitle data-route-heading className="text-3xl">
							Published reader documents
						</CardTitle>
						<CardDescription className="max-w-3xl text-base">
							The reader surface turns one frozen consumption batch into a
							readable document layer. Merge docs and singleton polish docs now
							live on the same frontstage, while yellow-warning documents stay
							honest about missing or degraded source evidence.
						</CardDescription>
					</CardHeader>
					<CardContent className="flex flex-wrap gap-3">
						<Button asChild>
							<Link href="/subscriptions">Open source intake</Link>
						</Button>
						<Button asChild variant="secondary">
							<Link href="/trends">Open trends</Link>
						</Button>
						<Button asChild variant="outline">
							<Link href="/briefings">Open briefings</Link>
						</Button>
					</CardContent>
				</Card>
				<Card className="border-border/70">
					<CardHeader>
						<CardTitle className="text-xl">Navigation brief</CardTitle>
						<CardDescription>
							The 30-second guide over the current published-doc layer.
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
											className="block rounded-lg border border-border/60 p-3 transition hover:bg-muted/40"
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

			<section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
				{documents.length ? (
					documents.map((document) => (
						<Card key={document.id} className="border-border/70">
							<CardHeader className="space-y-3">
								<div className="flex flex-wrap items-center gap-2">
									<Badge variant="secondary">
										{document.materialization_mode}
									</Badge>
									<Badge
										variant={
											document.published_with_gap ? "destructive" : "outline"
										}
									>
										{document.published_with_gap ? "Yellow warning" : "Clear"}
									</Badge>
								</div>
								<div>
									<CardTitle className="text-xl">{document.title}</CardTitle>
									<CardDescription className="mt-2">
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
										.slice(0, 3)
										.map((source) => (
											<div
												key={String(source.source_item_id ?? source.title)}
												className="rounded-lg border border-border/60 p-3 text-sm"
											>
												<p className="font-medium">
													{typeof source.title === "string"
														? source.title
														: "Untitled source"}
												</p>
												{typeof source.digest_preview === "string" ? (
													<p className="mt-1 text-muted-foreground">
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
					))
				) : (
					<Card className="border-border/70 md:col-span-2 xl:col-span-3">
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
