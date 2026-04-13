"use client";

import Link from "next/link";
import type { CSSProperties } from "react";
import { SourceIdentityCard } from "@/components/source-identity-card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { DigestFeedItem, SubscriptionCategory } from "@/lib/api/types";
import {
	editorialMono,
	editorialSans,
	editorialSerif,
} from "@/lib/editorial-fonts";
import { resolveFeedIdentity } from "@/lib/source-identity";
import { cn } from "@/lib/utils";

import { RelativeTime } from "./relative-time";

const CATEGORY_LABELS: Record<SubscriptionCategory, string> = {
	tech: "Tech",
	creator: "Creator",
	macro: "Macro",
	ops: "Ops",
	misc: "Misc",
};

function toSourceLabel(source: string): string {
	const normalized = source.trim().toLowerCase();
	if (normalized === "youtube") return "YouTube";
	if (normalized === "bilibili") return "Bilibili";
	if (normalized === "rss" || normalized === "rss_generic") return "RSS";
	return source || "Unknown";
}

function renderSourceName(source: string, sourceName: string): string {
	const fallback = toSourceLabel(source);
	const name = sourceName.trim();
	if (!name || name.toLowerCase() === source.trim().toLowerCase()) {
		return fallback;
	}
	return `${fallback} · ${name}`;
}

type EntryListItem = DigestFeedItem & { href: string };

type EntryListProps = {
	items: EntryListItem[];
	selectedJobId: string | null;
};

export function EntryList({ items, selectedJobId }: EntryListProps) {
	return (
		<aside
			className={`feed-entry-column ${editorialSans.className}`}
			aria-label="Entry list"
		>
			<h2 className="sr-only">Digest entry list</h2>
			<ScrollArea className="feed-entry-scroll">
				<ul className="feed-entry-list">
					{items.map((item, index) => {
						const isVideo = (item.content_type ?? "video") === "video";
						const isSelected = selectedJobId === item.job_id;
						const identityModel = resolveFeedIdentity(item);
						const staggerStyle = {
							"--feed-stagger-index": index,
						} as CSSProperties;

						return (
							<li
								key={item.feed_id}
								className="feed-entry-item"
								style={staggerStyle}
							>
								<Link
									href={item.href}
									className={cn("feed-entry-link", isSelected && "is-selected")}
									aria-current={isSelected ? "true" : undefined}
								>
									<div className="space-y-3">
										<div className="flex flex-wrap items-center gap-2">
											<span
												className={cn(
													"feed-entry-type-pill",
													isVideo
														? "feed-entry-type-video"
														: "feed-entry-type-article",
												)}
											>
												{isVideo ? "Video" : "Article"}
											</span>
											<Badge
												variant="secondary"
												className="feed-entry-category-badge"
												data-category={item.category}
											>
												{CATEGORY_LABELS[item.category] ?? item.category}
											</Badge>
											{item.saved ? (
												<Badge variant="outline">Saved</Badge>
											) : null}
											{item.feedback_label ? (
												<Badge variant="outline">{item.feedback_label}</Badge>
											) : null}
										</div>
										<div className="space-y-2">
											<p
												className={`feed-entry-kicker ${editorialMono.className}`}
											>
												{renderSourceName(item.source, item.source_name)}
												<span aria-hidden="true"> · </span>
												<RelativeTime dateTime={item.published_at} />
											</p>
											<h3
												className={`feed-entry-headline ${editorialSerif.className}`}
											>
												{item.title}
											</h3>
											{item.published_document_title ? (
												<p className="feed-entry-support">
													Reader edition ready · {item.published_document_title}
												</p>
											) : null}
										</div>
										<SourceIdentityCard
											identity={{
												...identityModel,
												description: identityModel.description,
												meta: [
													`Universe ${renderSourceName(item.source, item.source_name)}`,
													`Published ${new Date(
														item.published_at,
													).toLocaleDateString("en-US", {
														month: "short",
														day: "numeric",
														year: "numeric",
													})}`,
													...(item.feedback_label
														? [`Feedback ${item.feedback_label}`]
														: []),
												],
											}}
											compact
											className={cn(
												"feed-entry-identity-card transition-colors",
												isSelected &&
													"border-primary/45 bg-[color:var(--color-primary-light)]/50",
											)}
										/>
									</div>
								</Link>
							</li>
						);
					})}
				</ul>
			</ScrollArea>
		</aside>
	);
}
