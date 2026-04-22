import type { Metadata } from "next";
import Link from "next/link";

import { getActionSessionTokenForForm } from "@/app/action-security";
import { getFlashMessage, toErrorCode } from "@/app/flash-message";
import { EntryList } from "@/components/entry-list";
import { FeedFeedbackPanel } from "@/components/feed-feedback-panel";
import { FormSelectField } from "@/components/form-field";
import { ReadingPane } from "@/components/reading-pane";
import { SourceIdentityCard } from "@/components/source-identity-card";
import { SyncNowButton } from "@/components/sync-now-button";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api/client";
import { editorialSans, editorialSerif } from "@/lib/editorial-fonts";
import { getLocaleMessages } from "@/lib/i18n/messages";
import {
	resolveSearchParams,
	type SearchParamsInput,
} from "@/lib/search-params";
import { buildProductMetadata } from "@/lib/seo";
import {
	resolveFeedDisplaySourceName,
	resolveFeedDisplayTitle,
	resolveSubscriptionIdentity,
} from "@/lib/source-identity";

const feedCopy = getLocaleMessages().feedPage;

export const metadata: Metadata = buildProductMetadata({
	title: feedCopy.metadataTitle,
	description: feedCopy.metadataDescription,
	route: "feed",
});

type FeedPageProps = {
	searchParams?: SearchParamsInput;
};

const CATEGORY_KEYS = ["tech", "creator", "macro", "ops", "misc"] as const;
const SOURCE_KEYS = ["youtube", "bilibili", "rss"] as const;
const FEEDBACK_KEYS = [
	"saved",
	"useful",
	"noisy",
	"dismissed",
	"archived",
] as const;

type FeedFeedbackFilter = (typeof FEEDBACK_KEYS)[number] | "";

const SORT_KEYS = ["recent", "curated"] as const;

type FeedSortMode = (typeof SORT_KEYS)[number];

type FeedUiItem = Awaited<
	ReturnType<typeof apiClient.getDigestFeed>
>["items"][number] & {
	uiDisplayTitle?: string | null;
	uiDisplaySourceName?: string | null;
};

function toSourceSelectValue(
	source: string,
): "" | (typeof SOURCE_KEYS)[number] {
	const normalized = source.trim().toLowerCase();
	if (
		normalized === "youtube" ||
		normalized === "bilibili" ||
		normalized === "rss"
	) {
		return normalized;
	}
	if (normalized === "rss_generic") {
		return "rss";
	}
	return "";
}

function toSourceLabel(source: string): string {
	const normalized = source.trim().toLowerCase();
	if (normalized === "youtube") return "YouTube";
	if (normalized === "bilibili") return "Bilibili";
	if (normalized === "rss" || normalized === "rss_generic") return "RSS";
	return source || "Unknown";
}

function formatPublishedDateLabel(
	value: string | undefined,
): string | undefined {
	if (!value) return undefined;
	const parsed = new Date(value);
	if (Number.isNaN(parsed.getTime())) return value;
	return new Intl.DateTimeFormat("en-US", {
		year: "numeric",
		month: "long",
		day: "numeric",
		timeZone: "UTC",
	}).format(parsed);
}

function looksLikeOpaqueVideoId(
	value: string | null | undefined,
	source: string | null | undefined,
): boolean {
	const text = String(value || "").trim();
	const normalizedSource = String(source || "")
		.trim()
		.toLowerCase();
	if (!text) return false;
	if (normalizedSource === "youtube") {
		return /^[A-Za-z0-9_-]{11}$/.test(text);
	}
	if (normalizedSource === "bilibili") {
		return /^BV[0-9A-Za-z]{10,}$/i.test(text) || /^av\d+$/i.test(text);
	}
	return false;
}

function extractMeaningfulHeading(markdown: string): string | null {
	const lines = markdown.split("\n");
	for (const line of lines) {
		const match = line.match(/^(#{1,2})\s+(.+)$/);
		if (!match) continue;
		const text = match[2].trim();
		if (!text || /^https?:\/\//i.test(text)) continue;
		return text;
	}
	return null;
}

export default async function FeedPage({ searchParams }: FeedPageProps) {
	const copy = getLocaleMessages().feedPage;
	const categoryLabels: Record<(typeof CATEGORY_KEYS)[number], string> = {
		tech: copy.categoryOptions.tech,
		creator: copy.categoryOptions.creator,
		macro: copy.categoryOptions.macro,
		ops: copy.categoryOptions.ops,
		misc: copy.categoryOptions.misc,
	};
	const sourceOptions = [
		{ value: "", label: copy.sourceOptions.all },
		...SOURCE_KEYS.map((value) => ({
			value,
			label: copy.sourceOptions[value],
		})),
	] as const;
	const feedbackOptions = [
		{ value: "", label: copy.feedbackOptions.all },
		...FEEDBACK_KEYS.map((value) => ({
			value,
			label: copy.feedbackOptions[value],
		})),
	] as const;
	const sortOptions = SORT_KEYS.map((value) => ({
		value,
		label: copy.sortOptions[value],
	}));
	const sessionToken = getActionSessionTokenForForm();
	const {
		source,
		category,
		feedback,
		sort,
		sub,
		limit,
		cursor,
		prev_cursor,
		page,
		item,
	} = await resolveSearchParams(searchParams, [
		"source",
		"category",
		"feedback",
		"sort",
		"sub",
		"limit",
		"cursor",
		"prev_cursor",
		"page",
		"item",
	]);

	const parsedLimit = Number.parseInt(limit, 10);
	const safeLimit =
		Number.isFinite(parsedLimit) && parsedLimit > 0
			? Math.min(parsedLimit, 100)
			: 20;
	const safeCursor = cursor.trim() || undefined;
	const safePrevCursor = prev_cursor.trim() || undefined;
	const parsedPage = Number.parseInt(page, 10);
	const inferredPage = safeCursor ? 2 : 1;
	const safePage =
		Number.isFinite(parsedPage) && parsedPage > 0 ? parsedPage : inferredPage;
	const normalizedSource = source.trim().toLowerCase();
	const safeSource = normalizedSource || undefined;
	const normalizedFeedback = feedback.trim().toLowerCase();
	const safeFeedback: FeedFeedbackFilter =
		normalizedFeedback === "saved" ||
		normalizedFeedback === "useful" ||
		normalizedFeedback === "noisy" ||
		normalizedFeedback === "dismissed" ||
		normalizedFeedback === "archived"
			? normalizedFeedback
			: "";
	const normalizedSort = sort.trim().toLowerCase();
	const safeSort: FeedSortMode =
		normalizedSort === "curated" ? "curated" : "recent";
	const safeSubscriptionId = sub.trim() || undefined;
	const sourceSelectValue = toSourceSelectValue(source);
	const isFiltered = Boolean(
		safeSource ||
			category ||
			safeFeedback ||
			safeSubscriptionId ||
			safeSort !== "recent",
	);
	const hasVisibleFilterLabel = Boolean(
		safeSource ||
			category ||
			safeFeedback ||
			safeSubscriptionId ||
			safeSort !== "recent",
	);
	const requestedJobId = item.trim() || null;

	let feed: Awaited<ReturnType<typeof apiClient.getDigestFeed>> | null = null;
	let selectedFeedback: Awaited<
		ReturnType<typeof apiClient.getFeedFeedback>
	> | null = null;
	let activeSubscription:
		| Awaited<ReturnType<typeof apiClient.listSubscriptions>>[number]
		| null = null;
	let errorCode: string | null = null;
	try {
		const query: Parameters<typeof apiClient.getDigestFeed>[0] = {
			limit: safeLimit,
			cursor: safeCursor,
		};
		if (safeSource) {
			query.source = safeSource;
		}
		if (CATEGORY_KEYS.includes(category as (typeof CATEGORY_KEYS)[number])) {
			query.category = category as (typeof CATEGORY_KEYS)[number];
		}
		if (safeFeedback) {
			query.feedback = safeFeedback;
		}
		if (safeSort !== "recent") {
			query.sort = safeSort;
		}
		if (safeSubscriptionId) {
			query.subscription_id = safeSubscriptionId;
		}
		feed = await apiClient.getDigestFeed(query);
		if (safeSubscriptionId) {
			try {
				const subscriptions = await apiClient.listSubscriptions({
					enabled_only: false,
				});
				activeSubscription =
					subscriptions.find(
						(subscription) =>
							String(subscription.id || "").trim() === safeSubscriptionId,
					) ?? null;
			} catch {
				activeSubscription = null;
			}
		}
	} catch (err) {
		errorCode = toErrorCode(err);
	}

	const items = feed?.items ?? [];
	const nextCursor = feed?.next_cursor ?? null;
	const isFirstPage = !safeCursor;

	const buildPageUrl = ({
		cursorValue,
		prevCursorValue,
		pageValue,
		itemValue,
	}: {
		cursorValue?: string;
		prevCursorValue?: string;
		pageValue: number;
		itemValue?: string;
	}) => {
		const params = new URLSearchParams();
		if (safeSource) params.set("source", safeSource);
		if (category) params.set("category", category);
		if (safeFeedback) params.set("feedback", safeFeedback);
		if (safeSort !== "recent") params.set("sort", safeSort);
		if (safeSubscriptionId) params.set("sub", safeSubscriptionId);
		if (safeLimit !== 20) params.set("limit", String(safeLimit));
		if (pageValue > 1) params.set("page", String(pageValue));
		if (cursorValue) params.set("cursor", cursorValue);
		if (prevCursorValue) params.set("prev_cursor", prevCursorValue);
		if (itemValue) params.set("item", itemValue);
		const qs = params.toString();
		return `/feed${qs ? `?${qs}` : ""}`;
	};

	const buildItemUrl = ({ item: itemId }: { item?: string }) =>
		buildPageUrl({
			cursorValue: safeCursor,
			prevCursorValue: safePrevCursor,
			pageValue: safePage,
			itemValue: itemId ?? undefined,
		});

	const selectedItem = requestedJobId
		? items.find((feedItem) => feedItem.job_id === requestedJobId)
		: null;
	const itemsNeedingTitleHelp = items
		.filter(
			(item) =>
				looksLikeOpaqueVideoId(item.title, item.source) &&
				!item.published_document_title,
		)
		.slice(0, 8);
	const titleOverrides = new Map<string, string>();
	await Promise.all(
		itemsNeedingTitleHelp.map(async (item) => {
			try {
				const payload = await apiClient.getArtifactMarkdown({
					job_id: item.job_id,
					include_meta: true,
				});
				const title = extractMeaningfulHeading(payload.markdown);
				if (title) {
					titleOverrides.set(item.job_id, title);
				}
			} catch {
				// Keep the fallback title path if the artifact fetch fails.
			}
		}),
	);
	const enhancedItems: FeedUiItem[] = items.map((item) => ({
		...item,
		uiDisplayTitle: titleOverrides.get(item.job_id) ?? null,
		uiDisplaySourceName: item.canonical_source_name ?? item.source_name ?? null,
	}));
	const effectiveSelectedItem = selectedItem
		? (enhancedItems.find((item) => item.job_id === selectedItem.job_id) ??
			selectedItem)
		: (enhancedItems[0] ?? null);
	const effectiveSelectedJobId = effectiveSelectedItem?.job_id ?? null;
	const effectiveSelectedTitle = effectiveSelectedItem
		? resolveFeedDisplayTitle(effectiveSelectedItem)
		: undefined;
	const effectiveSelectedSourceName = effectiveSelectedItem
		? resolveFeedDisplaySourceName(effectiveSelectedItem)
		: undefined;
	const leadReadingHref =
		effectiveSelectedItem?.reader_route?.trim() ||
		(effectiveSelectedJobId
			? buildItemUrl({ item: effectiveSelectedJobId })
			: "/feed");
	const retryHref = buildPageUrl({
		cursorValue: safeCursor,
		prevCursorValue: safePrevCursor,
		pageValue: safePage,
		itemValue: effectiveSelectedJobId ?? undefined,
	});

	if (effectiveSelectedJobId && !errorCode) {
		try {
			selectedFeedback = await apiClient.getFeedFeedback(
				effectiveSelectedJobId,
			);
		} catch {
			selectedFeedback = null;
		}
	}

	return (
		<div
			className={`folo-page-shell folo-unified-shell ${editorialSans.className}`}
		>
			<div className="folo-page-header">
				<div className="folo-page-title-row">
					<div>
						<p className="folo-page-kicker">{copy.kicker}</p>
						<h1
							className={`folo-page-title ${editorialSerif.className}`}
							data-route-heading
							tabIndex={-1}
						>
							{copy.heroTitle}
						</h1>
						<p className="folo-page-subtitle">{copy.heroSubtitle}</p>
					</div>
					<div className="folo-page-toolbar flex-wrap">
						{effectiveSelectedJobId ? (
							<Button asChild variant="hero" data-interaction="cta">
								<Link href={leadReadingHref}>Start with this story</Link>
							</Button>
						) : null}
						<SyncNowButton sessionToken={sessionToken} prominence="secondary" />
					</div>
				</div>
			</div>

			{errorCode ? (
				<>
					<p
						className="alert alert-enter error"
						role="alert"
						aria-live="assertive"
					>
						{getFlashMessage(errorCode)}
					</p>
					<Button
						asChild
						variant="surface"
						size="sm"
						data-interaction="link-muted"
					>
						<Link href={retryHref}>{copy.retryCurrentPageButton}</Link>
					</Button>
				</>
			) : null}

			{!errorCode && items.length === 0 ? (
				<section className="folo-panel folo-surface folo-empty-panel">
					<p className="folo-empty-title">{copy.emptyTitle}</p>
					<p className="folo-empty-description">
						{isFiltered ? copy.emptyFiltered : copy.emptyUnfiltered}
					</p>
					{isFiltered ? (
						<Button
							asChild
							variant="outline"
							size="sm"
							data-interaction="link-muted"
						>
							<Link
								href={
									effectiveSelectedJobId
										? `/feed?item=${encodeURIComponent(effectiveSelectedJobId)}`
										: "/feed"
								}
							>
								{copy.clearButton}
							</Link>
						</Button>
					) : null}
					{!isFiltered ? (
						<Button asChild variant="hero" size="sm" data-interaction="cta">
							<Link href="/subscriptions">{copy.goToSubscriptionsButton}</Link>
						</Button>
					) : null}
				</section>
			) : (
				<div className="feed-main-flow">
					<EntryList
						items={enhancedItems.map((feedItem) => ({
							...feedItem,
							href: buildItemUrl({ item: feedItem.job_id }),
						}))}
						selectedJobId={effectiveSelectedJobId}
					/>
					<div className="space-y-4">
						<ReadingPane
							jobId={effectiveSelectedJobId}
							title={effectiveSelectedTitle}
							source={effectiveSelectedItem?.source}
							sourceName={effectiveSelectedSourceName}
							videoUrl={effectiveSelectedItem?.video_url}
							publishedAt={effectiveSelectedItem?.published_at}
							publishedDateLabel={formatPublishedDateLabel(
								effectiveSelectedItem?.published_at,
							)}
							identity={effectiveSelectedItem ?? undefined}
						/>
						{effectiveSelectedJobId ? (
							<details className="rounded-2xl border border-border/60 bg-background/72 p-4">
								<summary className="cursor-pointer list-none font-semibold text-foreground">
									React to this item
								</summary>
								<div className="mt-4">
									<FeedFeedbackPanel
										initialFeedback={selectedFeedback}
										jobId={effectiveSelectedJobId}
										sessionToken={sessionToken}
									/>
								</div>
							</details>
						) : null}
						<details
							className="rounded-2xl border border-border/60 bg-background/72 p-4"
							open={isFiltered}
						>
							<summary className="cursor-pointer list-none font-semibold text-foreground">
								Desk notes and filters
							</summary>
							<div className="mt-4 space-y-4">
								<p className="text-sm leading-6 text-muted-foreground">
									Keep the desk quiet. Open filters only when the list feels too
									wide or you need to react to one item.
								</p>
								{activeSubscription ? (
									<details className="rounded-2xl border border-border/60 bg-background/80 p-4">
										<summary className="cursor-pointer list-none text-sm font-medium text-foreground">
											Pinned source
										</summary>
										<div className="mt-3">
											<SourceIdentityCard
												identity={resolveSubscriptionIdentity(
													activeSubscription,
												)}
												compact
											/>
										</div>
									</details>
								) : null}
								<form
									method="GET"
									className="feed-filter-form"
									aria-label={copy.filterRegionLabel}
								>
									<input
										type="hidden"
										name="item"
										value={effectiveSelectedJobId ?? ""}
									/>
									<div className="feed-filter-selects">
										<FormSelectField
											name="source"
											label={copy.filterLabels.source}
											defaultValue={sourceSelectValue}
											options={sourceOptions.map((option) => ({
												value: option.value,
												label: option.label,
											}))}
											fieldClassName="feed-filter-field"
											labelClassName="sr-only"
											selectClassName="feed-filter-select"
										/>
										<FormSelectField
											name="category"
											label={copy.filterLabels.category}
											defaultValue={category}
											options={[
												{ value: "", label: copy.categoryOptions.all },
												...Object.entries(categoryLabels).map(
													([key, value]) => ({
														value: key,
														label: value,
													}),
												),
											]}
											fieldClassName="feed-filter-field"
											labelClassName="sr-only"
											selectClassName="feed-filter-select"
										/>
										<FormSelectField
											name="feedback"
											label={copy.filterLabels.feedback}
											defaultValue={safeFeedback}
											options={feedbackOptions.map((option) => ({
												value: option.value,
												label: option.label,
											}))}
											fieldClassName="feed-filter-field"
											labelClassName="sr-only"
											selectClassName="feed-filter-select"
										/>
										<FormSelectField
											name="sort"
											label={copy.filterLabels.sort}
											defaultValue={safeSort}
											options={sortOptions.map((option) => ({
												value: option.value,
												label: option.label,
											}))}
											fieldClassName="feed-filter-field"
											labelClassName="sr-only"
											selectClassName="feed-filter-select"
										/>
									</div>
									{safeSubscriptionId ? (
										<input
											type="hidden"
											name="sub"
											value={safeSubscriptionId}
										/>
									) : null}
									<input type="hidden" name="limit" value={String(safeLimit)} />
									<div className="feed-filter-actions">
										<Button
											type="submit"
											variant="outline"
											size="sm"
											data-interaction="control"
											data-testid="feed-filter-submit"
										>
											{copy.filterButton}
										</Button>
										{isFiltered ? (
											<Button
												asChild
												variant="ghost"
												size="sm"
												className="feed-filter-clear"
												data-testid="feed-filter-clear"
											>
												<Link
													href={
														effectiveSelectedJobId
															? `/feed?item=${encodeURIComponent(effectiveSelectedJobId)}`
															: "/feed"
													}
												>
													{copy.clearButton}
												</Link>
											</Button>
										) : null}
									</div>
								</form>
							</div>
						</details>
					</div>
				</div>
			)}

			{!errorCode && items.length > 0 ? (
				<nav
					className="folo-panel folo-surface folo-pagination-shell"
					aria-label={copy.paginationLabel}
				>
					<div className="folo-pagination-group">
						{!isFirstPage ? (
							<Button asChild variant="surface" size="sm">
								<Link
									href={buildPageUrl({
										cursorValue: safePrevCursor,
										pageValue: Math.max(1, safePage - 1),
										itemValue: effectiveSelectedJobId ?? undefined,
									})}
								>
									{copy.previousPageButton}
								</Link>
							</Button>
						) : null}
						{isFiltered && hasVisibleFilterLabel ? (
							<span className="folo-filter-label">
								{safeSource && `${toSourceLabel(safeSource)}`}
								{safeSource && category ? " · " : ""}
								{category &&
									`${categoryLabels[category as keyof typeof categoryLabels] ?? category}`}
								{(safeSource || category) && safeFeedback ? " · " : ""}
								{safeFeedback &&
									`${feedbackOptions.find((option) => option.value === safeFeedback)?.label ?? safeFeedback}`}
								{(safeSource || category || safeFeedback) && safeSubscriptionId
									? " · "
									: ""}
								{safeSubscriptionId ? copy.subscriptionFilterLabel : ""}
								{(safeSource ||
									category ||
									safeFeedback ||
									safeSubscriptionId) &&
								safeSort !== "recent"
									? " · "
									: ""}
								{safeSort !== "recent"
									? `${sortOptions.find((option) => option.value === safeSort)?.label ?? safeSort}`
									: ""}
							</span>
						) : null}
					</div>
					<div className="folo-pagination-group">
						<span className="folo-filter-label">
							{copy.pagePrefix} {safePage}
						</span>
						{nextCursor !== null ? (
							<Button asChild variant="surface" size="sm">
								<Link
									href={buildPageUrl({
										cursorValue: nextCursor,
										prevCursorValue: safeCursor,
										pageValue: safePage + 1,
										itemValue: effectiveSelectedJobId ?? undefined,
									})}
								>
									{copy.nextPageButton}
								</Link>
							</Button>
						) : null}
					</div>
				</nav>
			) : null}
		</div>
	);
}
