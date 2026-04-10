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

	return (
		<main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-8 md:px-6">
			<section className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
				<div className="space-y-3">
					<div className="flex flex-wrap items-center gap-2">
						<Badge variant="secondary">{document.materialization_mode}</Badge>
						<Badge
							variant={document.published_with_gap ? "destructive" : "outline"}
						>
							{document.published_with_gap ? "Yellow warning" : "Clear"}
						</Badge>
						{document.topic_label ? (
							<Badge variant="outline">{document.topic_label}</Badge>
						) : null}
					</div>
					<h1 data-route-heading className="text-3xl font-semibold">
						{document.title}
					</h1>
					<p className="max-w-4xl text-muted-foreground">
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
						<Link href="/trends">Open trends</Link>
					</Button>
				</div>
			</section>

			{document.published_with_gap ? (
				<YellowWarningCard reasons={document.warning.reasons} />
			) : null}

			<section className="grid gap-6 lg:grid-cols-[1.65fr_1fr]">
				<Card className="border-border/70">
					<CardHeader>
						<CardTitle>Reader body</CardTitle>
						<CardDescription>
							The published markdown unit. Merge docs and singleton docs both
							render through this same surface.
						</CardDescription>
					</CardHeader>
					<CardContent>
						<div className="markdown-body">
							<MarkdownPreview markdown={document.markdown} />
						</div>
					</CardContent>
				</Card>

				<div className="space-y-6">
					<SourceContributionDrawer document={document} />
					<Card className="border-border/70">
						<CardHeader>
							<CardTitle className="text-base">
								Coverage ledger snapshot
							</CardTitle>
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
