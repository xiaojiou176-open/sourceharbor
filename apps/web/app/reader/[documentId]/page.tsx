import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { MarkdownPreview } from "@/components/markdown-preview";
import { SourceContributionDrawer } from "@/components/source-contribution-drawer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { YellowWarningCard } from "@/components/yellow-warning-card";
import { apiClient } from "@/lib/api/client";
import { buildProductMetadata } from "@/lib/seo";

type ReaderDetailPageProps = {
	params: Promise<{ documentId: string }> | { documentId: string };
};

export async function generateMetadata({
	params,
}: ReaderDetailPageProps): Promise<Metadata> {
	const resolved = await params;
	return buildProductMetadata({
		title: `Reader document ${resolved.documentId}`,
		description:
			"Published reader document detail with markdown body, yellow warning state, and source contribution drawer.",
		route: "reader",
	});
}

export default async function ReaderDetailPage({
	params,
}: ReaderDetailPageProps) {
	const resolved = await params;
	const document = await apiClient
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
	const warningReasons = Array.isArray(document.warning?.reasons)
		? document.warning.reasons
		: [];

	return (
		<main className="mx-auto flex w-full max-w-7xl flex-col gap-8 px-4 py-8 md:px-6">
			<section className="space-y-4">
				<div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
					<Link
						href="/reader"
						className="inline-flex items-center gap-2 rounded-full border border-border/60 px-3 py-1 transition hover:bg-muted/40"
					>
						Back to reader
					</Link>
					<span>Reader frontstage</span>
					<span>/</span>
					<span>{document.topic_label ?? "Published document"}</span>
				</div>
				<div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
					<div className="space-y-3">
						<div className="flex flex-wrap items-center gap-2">
							<Badge variant="secondary">{document.materialization_mode}</Badge>
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
						<h1
							data-route-heading
							className="text-3xl font-semibold tracking-tight"
						>
							{document.title}
						</h1>
						<p className="max-w-4xl text-base leading-7 text-muted-foreground">
							{document.summary ??
								"This document unifies the reader-facing markdown, yellow-warning contract, and source contribution drawer for one published reader unit."}
						</p>
						<div className="flex flex-wrap gap-3 text-sm text-muted-foreground">
							<span>Window {document.window_id}</span>
							<span>Version {document.version}</span>
							<span>Sources {document.source_item_count}</span>
						</div>
					</div>
					<div className="flex flex-wrap gap-3">
						<Button asChild variant="outline">
							<Link href="/reader">Back to reader</Link>
						</Button>
						<Button asChild variant="secondary">
							<Link href="/search">Search evidence</Link>
						</Button>
					</div>
				</div>
			</section>

			<section className="grid gap-6 lg:grid-cols-[minmax(0,1.65fr)_minmax(320px,0.95fr)]">
				<Card className="border-border/70 shadow-sm">
					<CardHeader>
						<CardTitle>Reader body</CardTitle>
						<CardDescription>
							The published markdown unit. Merge docs and singleton docs both
							render through the same clean reading surface.
						</CardDescription>
					</CardHeader>
					<CardContent>
						<div className="mx-auto max-w-[72ch]">
							<MarkdownPreview markdown={document.markdown} />
						</div>
					</CardContent>
				</Card>

				<div className="space-y-6 lg:sticky lg:top-6">
					{document.published_with_gap ? (
						<YellowWarningCard reasons={warningReasons} />
					) : null}

					<Card className="border-border/70 shadow-sm">
						<CardHeader>
							<CardTitle className="text-base">Reader map</CardTitle>
							<CardDescription>
								A compact outline before you open the deeper evidence layers.
							</CardDescription>
						</CardHeader>
						<CardContent className="space-y-4 text-sm">
							<div className="flex flex-wrap gap-2">
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
							<div className="space-y-1 text-muted-foreground">
								<p>Window {document.window_id}</p>
								<p>Version {document.version}</p>
								<p>Sources {document.source_item_count}</p>
								<p>Sections {sections.length}</p>
							</div>
							{sections.length ? (
								<div className="rounded-xl border border-border/60 bg-muted/20 p-3">
									<p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
										Section outline
									</p>
									<ul className="mt-3 space-y-2">
										{sections.map((section) => (
											<li
												key={section.section_id}
												className="rounded-lg bg-background/90 p-3"
											>
												<p className="font-medium">{section.title}</p>
												<p className="mt-1 text-xs text-muted-foreground">
													Linked source items: {section.source_item_ids.length}
												</p>
											</li>
										))}
									</ul>
								</div>
							) : null}
						</CardContent>
					</Card>

					<SourceContributionDrawer document={document} />

					<Card className="border-border/70 shadow-sm">
						<CardHeader>
							<CardTitle className="text-base">
								Coverage ledger snapshot
							</CardTitle>
							<CardDescription>
								A quick integrity read before you reuse the document outside
								this reader surface.
							</CardDescription>
						</CardHeader>
						<CardContent className="space-y-2 text-sm">
							<p>
								Covered sources:{" "}
								{String(
									(coverageLedger as { covered_source_count?: number })
										.covered_source_count ?? "n/a",
								)}
							</p>
							<p>
								Gap sources:{" "}
								{String(
									(coverageLedger as { gap_source_count?: number })
										.gap_source_count ?? "n/a",
								)}
							</p>
							<p>
								Ledger kind:{" "}
								{String(
									(coverageLedger as { ledger_kind?: string }).ledger_kind ??
										"unknown",
								)}
							</p>
						</CardContent>
					</Card>
				</div>
			</section>
		</main>
	);
}
