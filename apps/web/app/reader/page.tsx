import { ArrowRight } from "lucide-react";
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

function looksLikeRawUrl(value: string | null | undefined): boolean {
	const text = String(value || "")
		.trim()
		.toLowerCase();
	return text.startsWith("http://") || text.startsWith("https://");
}

function isSingletonReadingMode(mode: string): boolean {
	return mode === "singleton_polish" || mode === "polish_only";
}

function humanizeReaderPlatform(
	platform: string | null | undefined,
	host: string | null | undefined,
): string {
	const normalized = String(platform || "")
		.trim()
		.toLowerCase();
	const normalizedHost = String(host || "")
		.trim()
		.toLowerCase();
	if (normalized === "youtube" || normalizedHost === "youtube.com")
		return "YouTube";
	if (normalized === "bilibili" || normalizedHost === "bilibili.com") {
		return "Bilibili";
	}
	if (normalized === "rss" || normalized === "rss_generic") return "RSS";
	return String(host || "").trim();
}

function isGenericSourceFallbackTitle(
	value: string | null | undefined,
): boolean {
	const normalized = String(value || "")
		.trim()
		.toLowerCase();
	if (!normalized) return false;
	if (normalized === "tracked source" || normalized === "reading source") {
		return true;
	}
	return normalized.endsWith(" source") && normalized.split(/\s+/).length <= 2;
}

function isGenericReaderShelfTitle(value: string | null | undefined): boolean {
	const normalized = String(value || "")
		.trim()
		.toLowerCase();
	return [
		"today lane",
		"reading today",
		"reading lane",
		"published story",
		"reading note",
		"finished story",
		"finished note",
	].includes(normalized);
}

function formatReaderShelfTitle(document: {
	title: string;
	topic_label?: string | null;
	materialization_mode: string;
	source_refs?: Array<Parameters<typeof resolveReaderSourceIdentity>[0]>;
}): string {
	const rawTitle = document.title.trim();
	if (
		rawTitle &&
		!looksLikeRawUrl(rawTitle) &&
		!isGenericReaderShelfTitle(rawTitle)
	) {
		return rawTitle || "Published story";
	}
	const topicLabel = String(document.topic_label || "").trim();
	if (topicLabel && !looksLikeRawUrl(topicLabel)) {
		return topicLabel;
	}
	const firstSource = Array.isArray(document.source_refs)
		? document.source_refs[0]
		: null;
	const sourcePlatform = String(firstSource?.platform || "").trim();
	const sourceTitle = firstSource
		? resolveReaderSourceIdentity(firstSource).title
		: "";
	const sourceHost =
		firstSource?.source_url && looksLikeRawUrl(firstSource.source_url)
			? (() => {
					try {
						return new URL(firstSource.source_url).hostname.replace(
							/^www\./,
							"",
						);
					} catch {
						return "";
					}
				})()
			: "";
	if (
		sourceTitle &&
		!looksLikeRawUrl(sourceTitle) &&
		!isGenericSourceFallbackTitle(sourceTitle)
	) {
		if (sourceHost && sourceTitle === sourceHost && sourcePlatform) {
			return `${humanizeReaderPlatform(sourcePlatform, sourceHost)} ${
				isSingletonReadingMode(document.materialization_mode) ? "note" : "story"
			}`;
		}
		return sourceTitle;
	}
	if (firstSource?.platform) {
		const platformLabel = humanizeReaderPlatform(sourcePlatform, sourceHost);
		if (platformLabel) {
			return `${platformLabel} ${
				isSingletonReadingMode(document.materialization_mode) ? "note" : "story"
			}`;
		}
		return isSingletonReadingMode(document.materialization_mode)
			? "Finished note"
			: "Finished story";
	}
	return isSingletonReadingMode(document.materialization_mode)
		? "Finished note"
		: "Finished story";
}

function formatReaderShelfSummary(document: {
	title: string;
	summary?: string | null;
	materialization_mode: string;
}) {
	const summary = String(document.summary ?? "").trim();
	if (
		summary &&
		!looksLikeRawUrl(summary) &&
		!summary.toLowerCase().includes("polish-only reader document")
	) {
		return summary;
	}
	return document.materialization_mode === "singleton_polish" ||
		document.materialization_mode === "polish_only"
		? "A finished reading note. Open notes later only when you need provenance."
		: "A finished story. Open notes later only when you need provenance.";
}

function formatReaderModeLabel(mode: string): string {
	if (mode === "merge_then_polish") return "Merged story";
	if (mode === "singleton_polish" || mode === "polish_only") {
		return "Single-source note";
	}
	if (mode === "repair_patch") return "Repaired story";
	return "Finished story";
}

function formatReaderCardMeta(document: {
	source_item_count: number;
	source_refs?: Array<Parameters<typeof resolveReaderSourceIdentity>[0]>;
}) {
	const sourceCountLabel = `${document.source_item_count} source${
		document.source_item_count === 1 ? "" : "s"
	}`;
	const firstSource = Array.isArray(document.source_refs)
		? document.source_refs[0]
		: null;
	if (!firstSource) return sourceCountLabel;
	const sourceIdentity = resolveReaderSourceIdentity(firstSource);
	const sourceLabel =
		sourceIdentity.subtitle && sourceIdentity.subtitle !== sourceIdentity.title
			? sourceIdentity.subtitle
			: sourceIdentity.title;
	return sourceLabel
		? `${sourceCountLabel} · ${sourceLabel}`
		: sourceCountLabel;
}

function formatReaderNavigationTitle(item: {
	title: string;
	platform?: string | null;
}): string {
	const rawTitle = String(item.title || "").trim();
	if (rawTitle && !looksLikeRawUrl(rawTitle)) return rawTitle;
	try {
		const host = new URL(rawTitle).hostname.replace(/^www\./, "");
		const platformLabel = humanizeReaderPlatform(item.platform, host);
		return platformLabel ? `${platformLabel} note` : "Finished story";
	} catch {
		return "Finished story";
	}
}

function formatReaderNavigationSummary(item: {
	title: string;
	summary?: string | null;
	platform?: string | null;
}): string | null {
	const summary = String(item.summary || "").trim();
	if (
		summary &&
		!looksLikeRawUrl(summary) &&
		!summary.toLowerCase().includes("polish-only reader")
	) {
		return summary;
	}
	try {
		const host = new URL(String(item.title || "").trim()).hostname.replace(
			/^www\./,
			"",
		);
		const platformLabel = humanizeReaderPlatform(item.platform, host) || host;
		return platformLabel
			? `Finished reading note from ${platformLabel}.`
			: null;
	} catch {
		return null;
	}
}

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
	const navigationItems =
		navigationBrief && Array.isArray(navigationBrief.items)
			? navigationBrief.items
			: [];

	const clearDocuments = documents.filter(
		(document) => !document.published_with_gap,
	);
	const leadDocument = clearDocuments[0] ?? documents[0] ?? null;
	const totalDocuments = documents.length;
	const shelfUnavailable = documentsUnavailable && totalDocuments === 0;
	const leadTitle = leadDocument ? formatReaderShelfTitle(leadDocument) : "";
	const leadSummary = leadDocument
		? formatReaderShelfSummary(leadDocument)
		: null;
	const needsAttentionDocuments = documents.filter(
		(document) =>
			document.published_with_gap && document.id !== (leadDocument?.id ?? ""),
	);
	const libraryDocuments = documents.filter(
		(document) =>
			document.id !== (leadDocument?.id ?? "") && !document.published_with_gap,
	);
	return (
		<div
			className={`mx-auto flex w-full max-w-[72rem] flex-col gap-10 px-4 py-8 md:px-6 ${editorialSans.className}`}
		>
			<section className="space-y-6">
				<Card className="overflow-hidden border-border/70 bg-gradient-to-br from-background via-background to-rose-50/60 shadow-sm dark:to-rose-950/10">
					<CardHeader className="space-y-7 pb-4">
						<div className="space-y-4">
							<h1
								data-route-heading
								tabIndex={-1}
								className={`max-w-4xl pb-1 text-4xl leading-[1.1] tracking-tight md:text-5xl md:leading-[1.02] xl:text-6xl ${editorialSerif.className}`}
							>
								{shelfUnavailable
									? "Reader shelf is temporarily unavailable"
									: leadDocument
										? leadTitle
										: "Reader"}
							</h1>
							<CardDescription className="max-w-3xl text-base leading-8 text-foreground/82">
								{shelfUnavailable
									? "The reading shelf could not be loaded just now. You can still open the sample story or check the backstage status while it recovers."
									: (leadSummary ??
										"Pick one finished story. Read first, then open notes only when you need provenance.")}
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
						{shelfUnavailable ? (
							<div className="rounded-[1.5rem] border border-border/60 bg-background/75 p-5 text-sm leading-7 text-foreground/75">
								This page is in fail-close mode. Open the sample story or the
								backstage status page, then come back once the live shelf
								recovers.
							</div>
						) : null}
						{leadDocument ? null : (
							<div className="grid gap-4 rounded-[1.75rem] border border-dashed border-border/70 bg-muted/20 p-6 md:grid-cols-[minmax(0,1.3fr)_minmax(260px,0.8fr)]">
								<div>
									<p className="text-sm uppercase tracking-[0.24em] text-muted-foreground">
										Start with one story
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
										Sample story
									</p>
									<p className="mt-3 text-sm leading-6 text-muted-foreground">
										Open one sample story first, then come back once the live
										shelf is ready.
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
			</section>

			{navigationBrief ? (
				<section className="space-y-4">
					<div className="flex items-end justify-between gap-3">
						<div>
							<h2 className="font-serif text-3xl tracking-tight">
								Keep reading
							</h2>
							<p className="text-sm text-muted-foreground">
								Use this only after you finish the story you opened first.
							</p>
						</div>
					</div>
					<div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
						{navigationItems.map((item, index) => (
							<Link
								key={item.document_id}
								href={item.route}
								className="block rounded-2xl border border-border/60 bg-background/95 p-4 shadow-sm transition hover:border-rose-200/80 hover:bg-muted/20"
							>
								<div className="flex items-start gap-3">
									<span className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-border/60 text-xs font-semibold text-muted-foreground">
										{String(index + 1).padStart(2, "0")}
									</span>
									<div className="min-w-0">
										<p className="font-medium">
											{formatReaderNavigationTitle(item)}
										</p>
										{item.summary ? (
											<p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
												{formatReaderNavigationSummary(item) ?? item.summary}
											</p>
										) : null}
									</div>
								</div>
							</Link>
						))}
					</div>
				</section>
			) : null}

			{needsAttentionDocuments.length ? (
				<section className="space-y-4">
					<div className="space-y-2">
						<h2 className="font-serif text-3xl tracking-tight">
							Read with notes nearby
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
											{formatReaderShelfTitle(document)}
										</CardTitle>
										<CardDescription className="mt-2 leading-6">
											{formatReaderShelfSummary(document) ??
												"Readable now, with one note to keep nearby while you read."}
										</CardDescription>
									</div>
								</CardHeader>
								<CardContent className="space-y-4">
									<div className="flex flex-wrap gap-2 text-sm text-muted-foreground">
										<span>{formatReaderCardMeta(document)}</span>
										<span>
											{formatReaderModeLabel(document.materialization_mode)}
										</span>
									</div>
									<Button asChild className="w-full">
										<Link href={`/reader/${document.id}`}>Open story</Link>
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
							Finished stories
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
											{formatReaderModeLabel(document.materialization_mode)}
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
											{formatReaderShelfTitle(document)}
										</CardTitle>
										<CardDescription className="mt-2 leading-6">
											{formatReaderShelfSummary(document) ??
												"Open the story to read it cleanly, then open notes only if you want more context."}
										</CardDescription>
									</div>
								</CardHeader>
								<CardContent className="space-y-4">
									<div className="flex flex-wrap gap-2 text-sm text-muted-foreground">
										<span>{formatReaderCardMeta(document)}</span>
									</div>
									<p className="text-sm text-muted-foreground">
										Open the finished take first. Notes and provenance stay
										below when you want a closer look.
									</p>
									<Button asChild className="w-full">
										<Link href={`/reader/${document.id}`}>Open story</Link>
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
