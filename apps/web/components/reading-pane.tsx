"use client";

import {
	ChevronDownIcon,
	ChevronRightIcon,
	ExternalLinkIcon,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { MarkdownPreview } from "@/components/markdown-preview";
import { SourceIdentityCard } from "@/components/source-identity-card";
import { Button } from "@/components/ui/button";
import {
	Collapsible,
	CollapsibleContent,
	CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ScrollArea } from "@/components/ui/scroll-area";
import { apiClient } from "@/lib/api/client";
import type { DigestFeedItem } from "@/lib/api/types";
import { sanitizeExternalUrl } from "@/lib/api/url";
import {
	editorialMono,
	editorialSans,
	editorialSerif,
} from "@/lib/editorial-fonts";
import { resolveFeedIdentity } from "@/lib/source-identity";

function extractHeadings(
	markdown: string,
): { level: number; text: string; id: string }[] {
	const headings: { level: number; text: string; id: string }[] = [];
	const lines = markdown.split("\n");
	for (const line of lines) {
		const match = line.match(/^(#{1,6})\s+(.+)$/);
		if (match) {
			const level = match[1].length;
			const text = match[2].trim();
			const id = text
				.toLowerCase()
				.replace(/\s+/g, "-")
				.replace(/[^\p{L}\p{N}-]/gu, "");
			headings.push({ level, text, id });
		}
	}
	return headings;
}

function toSourceLabel(source: string): string {
	const normalized = source.trim().toLowerCase();
	if (normalized === "youtube") return "YouTube";
	if (normalized === "bilibili") return "Bilibili";
	if (normalized === "rss" || normalized === "rss_generic") return "RSS";
	return source || "Unknown";
}

type ReadingPaneProps = {
	jobId: string | null;
	title?: string;
	source?: string;
	sourceName?: string;
	videoUrl?: string;
	publishedAt?: string;
	publishedDateLabel?: string;
	identity?: Pick<
		DigestFeedItem,
		| "source"
		| "source_name"
		| "canonical_source_name"
		| "canonical_author_name"
		| "subscription_id"
		| "affiliation_label"
		| "relation_kind"
		| "thumbnail_url"
		| "avatar_url"
		| "avatar_label"
		| "published_document_title"
		| "published_document_publish_status"
		| "published_with_gap"
		| "reader_route"
		| "video_url"
		| "title"
		| "category"
		| "content_type"
	>;
};

export function ReadingPane({
	jobId,
	title,
	source,
	sourceName,
	videoUrl,
	publishedAt,
	publishedDateLabel,
	identity,
}: ReadingPaneProps) {
	const [markdown, setMarkdown] = useState<string | null>(null);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState(false);
	const [reloadNonce, setReloadNonce] = useState(0);
	const [outlineOpen, setOutlineOpen] = useState(true);

	useEffect(() => {
		if (!jobId) {
			queueMicrotask(() => {
				setMarkdown(null);
				setError(false);
			});
			return;
		}
		let cancelled = false;
		const isRetry = reloadNonce > 0;
		queueMicrotask(() => {
			setLoading(true);
			setError(false);
			if (isRetry) {
				setMarkdown(null);
			}
		});
		apiClient
			.getArtifactMarkdown({ job_id: jobId, include_meta: true })
			.then((payload) => {
				if (cancelled) return;
				setMarkdown(payload.markdown);
				setLoading(false);
			})
			.catch(() => {
				if (cancelled) return;
				setError(true);
				setMarkdown(null);
				setLoading(false);
			});
		return () => {
			cancelled = true;
		};
	}, [jobId, reloadNonce]);

	if (!jobId) {
		return (
			<div
				className="feed-reading-pane-shell feed-reading-state"
				data-reading-state="empty"
			>
				<p className="feed-reading-state-title">
					Select an entry to read the digest and body
				</p>
				<p className="feed-reading-state-meta">
					Video and article items both support AI digest and outline views
				</p>
			</div>
		);
	}

	if (loading) {
		return (
			<div
				className="feed-reading-pane-shell feed-reading-state"
				data-reading-state="loading"
			>
				<div className="feed-reading-spinner" aria-hidden="true" />
				<p className="feed-reading-state-meta">Loading...</p>
			</div>
		);
	}

	if (error) {
		return (
			<div
				className="feed-reading-pane-shell feed-reading-state"
				data-reading-state="error"
			>
				<p className="feed-reading-error">
					Body content is temporarily unavailable. Please try again later.
				</p>
				<Button
					type="button"
					variant="link"
					className="btn-link h-auto p-0"
					onClick={() => {
						setError(false);
						setLoading(true);
						setReloadNonce((value) => value + 1);
					}}
					data-testid="reading-pane-retry"
				>
					Retry
				</Button>
			</div>
		);
	}

	const headings = markdown ? extractHeadings(markdown) : [];
	const safeVideoUrl = videoUrl ? sanitizeExternalUrl(videoUrl) : null;
	const safeReaderRoute = identity?.reader_route?.trim().startsWith("/reader/")
		? identity.reader_route.trim()
		: null;
	const sourceLabel = source ? toSourceLabel(source) : null;
	const identityModel = identity
		? resolveFeedIdentity({
				...identity,
				feed_id: jobId,
				job_id: jobId,
				published_at: publishedAt || "",
				summary_md: "",
				artifact_type: "digest",
			})
		: null;

	return (
		<div
			className={`feed-reading-pane-shell ${editorialSans.className}`}
			data-reading-state="content"
		>
			<ScrollArea className="flex-1">
				<article className="prose prose-sm dark:prose-invert reading-pane-prose feed-reading-article">
					<header className="feed-reading-header">
						<h2 className={`feed-reading-title ${editorialSerif.className}`}>
							{title || "Untitled"}
						</h2>
						<div className="feed-reading-meta">
							{sourceLabel ? (
								<span>
									{sourceName ? `${sourceLabel} · ${sourceName}` : sourceLabel}
								</span>
							) : null}
							{publishedAt ? (
								<time dateTime={publishedAt}>
									{publishedDateLabel ?? publishedAt}
								</time>
							) : null}
						</div>
						<div className="feed-reading-links">
							<Link
								href={`/jobs?job_id=${encodeURIComponent(jobId)}`}
								className={`feed-reading-link ${editorialMono.className}`}
								data-interaction="link-muted"
							>
								{jobId.slice(0, 8)}…
							</Link>
							{safeVideoUrl ? (
								<a
									href={safeVideoUrl}
									target="_blank"
									rel="noreferrer noopener"
									className={`feed-reading-link ${editorialMono.className}`}
									data-interaction="link-primary"
								>
									Open original
									<ExternalLinkIcon className="size-3" />
								</a>
							) : null}
							{safeReaderRoute ? (
								<Link
									href={safeReaderRoute}
									className={`feed-reading-link ${editorialMono.className}`}
									data-interaction="link-primary"
								>
									Open reader edition
								</Link>
							) : null}
						</div>
						{identity?.published_document_title ? (
							<p className={`feed-reading-link ${editorialMono.className}`}>
								Published unit · {identity.published_document_title}
								{identity.published_document_publish_status
									? ` · ${identity.published_document_publish_status}`
									: ""}
								{identity.published_with_gap ? " · with gap" : ""}
							</p>
						) : null}
						{identityModel ? (
							<div className="mt-4">
								<SourceIdentityCard identity={identityModel} compact />
							</div>
						) : null}
					</header>

					{headings.length > 0 ? (
						<Collapsible open={outlineOpen} onOpenChange={setOutlineOpen}>
							<CollapsibleTrigger className="feed-outline-trigger">
								{outlineOpen ? (
									<ChevronDownIcon className="size-4 text-muted-foreground" />
								) : (
									<ChevronRightIcon className="size-4 text-muted-foreground" />
								)}
								Outline
							</CollapsibleTrigger>
							<CollapsibleContent>
								<nav className="feed-outline-panel">
									<ul className="space-y-1.5">
										{headings.map((heading) => (
											<li
												key={heading.id}
												className="text-sm"
												style={{ paddingLeft: `${(heading.level - 1) * 14}px` }}
											>
												<a
													href={`#${heading.id}`}
													className="feed-outline-link"
													data-interaction="link-muted"
												>
													{heading.text}
												</a>
											</li>
										))}
									</ul>
								</nav>
							</CollapsibleContent>
						</Collapsible>
					) : null}

					{markdown ? (
						<div className="markdown-body">
							<MarkdownPreview markdown={markdown} />
						</div>
					) : (
						<p className="text-muted-foreground">No body content</p>
					)}
				</article>
			</ScrollArea>
		</div>
	);
}
