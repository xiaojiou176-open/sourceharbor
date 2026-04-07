"use client";

import Link from "next/link";
import type { CSSProperties } from "react";

import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { DigestFeedItem, SubscriptionCategory } from "@/lib/api/types";
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
		<aside className="feed-entry-column" aria-label="Entry list">
			<h2 className="sr-only">Digest entry list</h2>
			<ScrollArea className="feed-entry-scroll">
				<ul className="feed-entry-list">
					{items.map((item, index) => {
						const isVideo = (item.content_type ?? "video") === "video";
						const isSelected = selectedJobId === item.job_id;
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
									<div className="feed-entry-row">
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
										<div className="feed-entry-meta-wrap">
											<h3 className="feed-entry-title">{item.title}</h3>
											<div className="feed-entry-meta">
												<span className="feed-entry-source">
													{renderSourceName(item.source, item.source_name)}
												</span>
												<span>·</span>
												<RelativeTime dateTime={item.published_at} />
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
										</div>
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
