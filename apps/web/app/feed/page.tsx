import type { Metadata } from "next";
import Link from "next/link";

import { getActionSessionTokenForForm } from "@/app/action-security";
import { getFlashMessage, toErrorCode } from "@/app/flash-message";
import { EntryList } from "@/components/entry-list";
import { FeedFeedbackPanel } from "@/components/feed-feedback-panel";
import { FormSelectField } from "@/components/form-field";
import { ReadingPane } from "@/components/reading-pane";
import { SyncNowButton } from "@/components/sync-now-button";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api/client";
import { getLocaleMessages } from "@/lib/i18n/messages";
import {
	resolveSearchParams,
	type SearchParamsInput,
} from "@/lib/search-params";
import { buildProductMetadata } from "@/lib/seo";

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
	const selectedJobId = item.trim() || null;

	let feed: Awaited<ReturnType<typeof apiClient.getDigestFeed>> | null = null;
	let selectedFeedback: Awaited<
		ReturnType<typeof apiClient.getFeedFeedback>
	> | null = null;
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

	const retryHref = buildPageUrl({
		cursorValue: safeCursor,
		prevCursorValue: safePrevCursor,
		pageValue: safePage,
		itemValue: selectedJobId ?? undefined,
	});

	const selectedItem = selectedJobId
		? items.find((feedItem) => feedItem.job_id === selectedJobId)
		: null;
	if (selectedJobId && !errorCode) {
		try {
			selectedFeedback = await apiClient.getFeedFeedback(selectedJobId);
		} catch {
			selectedFeedback = null;
		}
	}

	return (
		<div className="folo-page-shell folo-unified-shell">
			<div className="folo-page-header">
				<div className="folo-page-title-row">
					<div>
						<p className="folo-page-kicker">{copy.kicker}</p>
						<h1 className="folo-page-title" data-route-heading>
							{copy.heroTitle}
						</h1>
						<p className="folo-page-subtitle">{copy.heroSubtitle}</p>
					</div>
					<div className="folo-page-toolbar">
						<SyncNowButton sessionToken={sessionToken} />
					</div>
				</div>
			</div>

			<section
				className="folo-panel folo-surface feed-filter-panel"
				aria-label={copy.filterRegionLabel}
			>
				<form method="GET" className="feed-filter-form">
					<input type="hidden" name="item" value={selectedJobId ?? ""} />
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
								...Object.entries(categoryLabels).map(([key, value]) => ({
									value: key,
									label: value,
								})),
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
						<input type="hidden" name="sub" value={safeSubscriptionId} />
					) : null}
					<input type="hidden" name="limit" value={String(safeLimit)} />
					<div className="feed-filter-actions">
						<Button
							type="submit"
							variant="hero"
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
										selectedJobId
											? `/feed?item=${encodeURIComponent(selectedJobId)}`
											: "/feed"
									}
								>
									{copy.clearButton}
								</Link>
							</Button>
						) : null}
					</div>
				</form>
			</section>

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
					{!isFiltered ? (
						<Button asChild variant="hero" size="sm" data-interaction="cta">
							<Link href="/subscriptions">{copy.goToSubscriptionsButton}</Link>
						</Button>
					) : null}
				</section>
			) : (
				<div className="feed-main-flow">
					<EntryList
						items={items.map((feedItem) => ({
							...feedItem,
							href: buildItemUrl({ item: feedItem.job_id }),
						}))}
						selectedJobId={selectedJobId}
					/>
					<div className="space-y-4">
						{selectedJobId ? (
							<FeedFeedbackPanel
								initialFeedback={selectedFeedback}
								jobId={selectedJobId}
								sessionToken={sessionToken}
							/>
						) : null}
						<ReadingPane
							jobId={selectedJobId}
							title={selectedItem?.title}
							source={selectedItem?.source}
							sourceName={selectedItem?.source_name}
							videoUrl={selectedItem?.video_url}
							publishedAt={selectedItem?.published_at}
							publishedDateLabel={formatPublishedDateLabel(
								selectedItem?.published_at,
							)}
							identity={selectedItem ?? undefined}
						/>
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
										itemValue: selectedJobId ?? undefined,
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
										itemValue: selectedJobId ?? undefined,
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
