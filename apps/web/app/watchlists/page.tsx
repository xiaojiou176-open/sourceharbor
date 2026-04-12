import type { Metadata } from "next";
import Link from "next/link";

import { getActionSessionTokenForForm } from "@/app/action-security";
import { getFlashMessage } from "@/app/flash-message";
import {
	deleteWatchlistAction,
	upsertWatchlistAction,
} from "@/app/watchlists/actions";
import {
	FormCheckboxField,
	FormInputField,
	FormSelectField,
} from "@/components/form-field";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { apiClient } from "@/lib/api/client";
import { formatDateTime } from "@/lib/format";
import { getLocaleMessages } from "@/lib/i18n/messages";
import {
	resolveSearchParams,
	type SearchParamsInput,
} from "@/lib/search-params";
import { buildProductMetadata } from "@/lib/seo";

const watchlistsCopy = getLocaleMessages().watchlistsPage;

export const metadata: Metadata = buildProductMetadata({
	title: watchlistsCopy.metadataTitle,
	description: watchlistsCopy.metadataDescription,
	route: "watchlists",
});

type WatchlistsPageProps = {
	searchParams?: SearchParamsInput;
};

export default async function WatchlistsPage({
	searchParams,
}: WatchlistsPageProps) {
	const copy = getLocaleMessages().watchlistsPage;
	const matcherOptions = [
		{ value: "topic_key", label: copy.matcherOptions.topicKey },
		{ value: "claim_kind", label: copy.matcherOptions.claimKind },
		{ value: "platform", label: copy.matcherOptions.platform },
		{ value: "source_match", label: copy.matcherOptions.sourceMatch },
	];
	const deliveryOptions = [
		{ value: "dashboard", label: copy.deliveryOptions.dashboard },
		{ value: "email", label: copy.deliveryOptions.email },
	];
	const matcherLabelMap = new Map(
		matcherOptions.map((option) => [option.value, option.label]),
	);
	const deliveryLabelMap = new Map(
		deliveryOptions.map((option) => [option.value, option.label]),
	);
	const {
		status,
		code,
		watchlist_id: watchlistId,
	} = await resolveSearchParams(searchParams, [
		"status",
		"code",
		"watchlist_id",
	] as const);
	const sessionToken = getActionSessionTokenForForm();

	const [watchlistsResult, opsResult] = await Promise.all([
		apiClient
			.listWatchlists()
			.then((items) => ({ items, error: false }))
			.catch(() => ({ items: [], error: true })),
		apiClient
			.getOpsInbox({ limit: 4, window_hours: 24 })
			.then((payload) => ({ payload, error: false }))
			.catch(() => ({ payload: null, error: true })),
	]);

	const watchlists = watchlistsResult.items;
	const editingWatchlist = watchlistId.trim()
		? (watchlists.find((item) => item.id === watchlistId.trim()) ?? null)
		: null;
	const trendWatchlist = editingWatchlist ?? watchlists[0] ?? null;
	const trendResult = trendWatchlist
		? await apiClient
				.getWatchlistTrend(trendWatchlist.id, {
					limit_runs: 3,
					limit_cards: 12,
				})
				.then((payload) => ({ payload, error: false }))
				.catch(() => ({ payload: null, error: true }))
		: { payload: null, error: false };
	const briefingPageResult = trendWatchlist
		? await apiClient
				.getWatchlistBriefingPage(trendWatchlist.id)
				.then((payload) => ({ payload, error: false }))
				.catch(() => ({ payload: null, error: true }))
		: { payload: null, error: false };
	const notificationGate = opsResult.payload?.gates.notifications ?? null;
	const selectedStory = briefingPageResult.payload?.selected_story ?? null;
	const selectedStoryRoutes =
		selectedStory?.routes ?? briefingPageResult.payload?.routes;
	const compounderFrontDoorHref = trendWatchlist
		? `/trends?watchlist_id=${encodeURIComponent(trendWatchlist.id)}`
		: "/trends";

	const alert =
		status && code ? (
			<p
				className={
					status === "error"
						? "alert alert-enter error"
						: "alert alert-enter success"
				}
				role={status === "error" ? "alert" : "status"}
				aria-live={status === "error" ? "assertive" : "polite"}
			>
				{getFlashMessage(code)}
			</p>
		) : null;

	return (
		<div className="folo-page-shell folo-unified-shell">
			<div className="folo-page-header">
				<p className="folo-page-kicker">{copy.kicker}</p>
				<h1 className="folo-page-title" data-route-heading tabIndex={-1}>
					{copy.heroTitle}
				</h1>
				<p className="folo-page-subtitle">{copy.heroSubtitle}</p>
			</div>

			{alert}

			<section className="grid gap-4 lg:grid-cols-[1.15fr_1fr]">
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<CardTitle>{copy.saveTitle}</CardTitle>
						<CardDescription>{copy.saveDescription}</CardDescription>
					</CardHeader>
					<CardContent>
						<form action={upsertWatchlistAction} className="grid gap-4">
							<input
								type="hidden"
								name="session_token"
								value={sessionToken}
								suppressHydrationWarning
							/>
							<input
								type="hidden"
								name="id"
								value={editingWatchlist?.id ?? ""}
								readOnly
							/>
							<FormInputField
								id="watchlist-name"
								name="name"
								label={copy.nameLabel}
								type="text"
								defaultValue={editingWatchlist?.name ?? ""}
								placeholder={copy.namePlaceholder}
								required
							/>
							<FormSelectField
								name="matcher_type"
								label={copy.watchTypeLabel}
								defaultValue={editingWatchlist?.matcher_type ?? "topic_key"}
								options={matcherOptions}
							/>
							<FormInputField
								id="watchlist-value"
								name="matcher_value"
								label={copy.matcherValueLabel}
								type="text"
								defaultValue={editingWatchlist?.matcher_value ?? ""}
								placeholder={copy.matcherValuePlaceholder}
								required
							/>
							<FormSelectField
								name="delivery_channel"
								label={copy.deliveryLabel}
								defaultValue={editingWatchlist?.delivery_channel ?? "dashboard"}
								options={deliveryOptions}
							/>
							<FormCheckboxField
								name="enabled"
								label={copy.enabledLabel}
								defaultChecked={editingWatchlist?.enabled ?? true}
							/>
							<div className="flex flex-wrap gap-3">
								<Button type="submit" variant="hero" size="sm">
									{editingWatchlist ? copy.updateButton : copy.saveButton}
								</Button>
								{editingWatchlist ? (
									<Button asChild variant="outline" size="sm">
										<Link href="/watchlists">{copy.createNewButton}</Link>
									</Button>
								) : null}
								<Button asChild variant="outline" size="sm">
									<Link
										href={
											editingWatchlist
												? `/trends?watchlist_id=${encodeURIComponent(editingWatchlist.id)}`
												: "/trends"
										}
									>
										{copy.openTrendViewButton}
									</Link>
								</Button>
								<Button asChild variant="outline" size="sm">
									<Link
										href={
											editingWatchlist
												? `/briefings?watchlist_id=${encodeURIComponent(editingWatchlist.id)}`
												: "/briefings"
										}
									>
										{copy.openBriefingButton}
									</Link>
								</Button>
							</div>
						</form>
					</CardContent>
				</Card>

				<Card className="folo-surface border-border/70">
					<CardHeader>
						<CardTitle>{copy.alertTitle}</CardTitle>
						<CardDescription>{copy.alertDescription}</CardDescription>
					</CardHeader>
					<CardContent className="space-y-3 text-sm text-muted-foreground">
						{notificationGate ? (
							<>
								<p>{notificationGate.summary}</p>
								<p>{notificationGate.next_step}</p>
							</>
						) : (
							<p>{copy.alertFallback}</p>
						)}
						<Button asChild variant="outline" size="sm">
							<Link href="/settings">
								{copy.openNotificationSettingsButton}
							</Link>
						</Button>
					</CardContent>
				</Card>
			</section>

			{trendWatchlist && briefingPageResult.payload ? (
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<CardTitle>Continue this watchlist</CardTitle>
						<CardDescription>
							Watchlists are the saved tracking objects. The unified compounder
							front door lives in Trends, where this watchlist turns into one
							current story, one recent-delta lane, and one internal evidence
							bundle path.
						</CardDescription>
					</CardHeader>
					<CardContent className="space-y-4">
						<div className="rounded-lg border border-border/60 bg-muted/20 p-4">
							<p className="font-medium text-foreground">
								{selectedStory?.headline ?? trendWatchlist.name}
							</p>
							<p className="mt-2 text-sm text-muted-foreground">
								{briefingPageResult.payload.briefing.summary.overview}
							</p>
							{briefingPageResult.payload.story_change_summary ? (
								<p className="mt-3 text-sm text-muted-foreground">
									{briefingPageResult.payload.story_change_summary}
								</p>
							) : null}
						</div>

						<div className="grid gap-3 text-sm text-muted-foreground sm:grid-cols-3">
							<div className="rounded-lg border border-border/60 bg-muted/20 p-3">
								<p className="font-medium text-foreground">Source families</p>
								<p className="mt-1">
									{briefingPageResult.payload.briefing.summary.source_count}
								</p>
							</div>
							<div className="rounded-lg border border-border/60 bg-muted/20 p-3">
								<p className="font-medium text-foreground">Recent runs</p>
								<p className="mt-1">
									{briefingPageResult.payload.briefing.summary.run_count}
								</p>
							</div>
							<div className="rounded-lg border border-border/60 bg-muted/20 p-3">
								<p className="font-medium text-foreground">Matched cards</p>
								<p className="mt-1">
									{briefingPageResult.payload.briefing.summary.matched_cards}
								</p>
							</div>
						</div>

						<div className="flex flex-wrap gap-3">
							<Button asChild variant="hero" size="sm">
								<Link href={compounderFrontDoorHref}>
									Open compounder front door
								</Link>
							</Button>
							{selectedStoryRoutes?.briefing ? (
								<Button asChild variant="outline" size="sm">
									<Link href={selectedStoryRoutes.briefing}>
										Open briefing story
									</Link>
								</Button>
							) : null}
							{briefingPageResult.payload.ask_route ? (
								<Button asChild variant="outline" size="sm">
									<Link href={briefingPageResult.payload.ask_route}>
										Ask about this story
									</Link>
								</Button>
							) : null}
							<Button asChild variant="outline" size="sm">
								<Link href="/playground">Review sample-proof boundary</Link>
							</Button>
						</div>
					</CardContent>
				</Card>
			) : null}

			<Card className="folo-surface border-border/70">
				<CardHeader>
					<CardTitle>{copy.currentTitle}</CardTitle>
					<CardDescription>{copy.currentDescription}</CardDescription>
				</CardHeader>
				<CardContent className="space-y-3">
					{watchlistsResult.error ? (
						<p className="text-sm text-muted-foreground">{copy.currentError}</p>
					) : watchlists.length === 0 ? (
						<p className="text-sm text-muted-foreground">{copy.currentEmpty}</p>
					) : (
						<ul className="space-y-3">
							{watchlists.map((item) => (
								<li
									key={item.id}
									className="rounded-lg border border-border/60 bg-muted/20 p-4"
								>
									<div className="flex flex-wrap items-center justify-between gap-3">
										<div className="space-y-1">
											<p className="font-medium">{item.name}</p>
											<p className="text-sm text-muted-foreground">
												{matcherLabelMap.get(item.matcher_type) ??
													item.matcher_type}
												: <code>{item.matcher_value}</code> ·{" "}
												{deliveryLabelMap.get(item.delivery_channel) ??
													item.delivery_channel}{" "}
												· {item.enabled ? copy.enabledState : copy.pausedState}
											</p>
											<p className="text-xs text-muted-foreground">
												{copy.updatedPrefix}: {formatDateTime(item.updated_at)}
											</p>
										</div>
										<div className="flex flex-wrap gap-3">
											<Button asChild variant="outline" size="sm">
												<Link
													href={`/watchlists?watchlist_id=${encodeURIComponent(item.id)}`}
												>
													{copy.editButton}
												</Link>
											</Button>
											<Button asChild variant="outline" size="sm">
												<Link
													href={`/trends?watchlist_id=${encodeURIComponent(item.id)}`}
												>
													{copy.viewTrendButton}
												</Link>
											</Button>
											<Button asChild variant="outline" size="sm">
												<Link
													href={`/briefings?watchlist_id=${encodeURIComponent(item.id)}`}
												>
													{copy.openBriefingButton}
												</Link>
											</Button>
											<form action={deleteWatchlistAction}>
												<input
													type="hidden"
													name="session_token"
													value={sessionToken}
													suppressHydrationWarning
												/>
												<input
													type="hidden"
													name="watchlist_id"
													value={item.id}
													readOnly
												/>
												<Button type="submit" variant="ghost" size="sm">
													{copy.deleteButton}
												</Button>
											</form>
										</div>
									</div>
								</li>
							))}
						</ul>
					)}
				</CardContent>
			</Card>

			{trendWatchlist && trendResult.payload ? (
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<CardTitle>{copy.recentMovementTitle}</CardTitle>
						<CardDescription>{copy.recentMovementDescription}</CardDescription>
					</CardHeader>
					<CardContent className="space-y-4">
						{trendResult.payload.timeline.map((run) => (
							<div
								key={run.job_id}
								className="rounded-lg border border-border/60 bg-muted/20 p-4"
							>
								<div className="flex flex-wrap items-center justify-between gap-3">
									<div className="space-y-1">
										<p className="font-medium">{run.title}</p>
										<p className="text-sm text-muted-foreground">
											{run.platform} · {formatDateTime(run.created_at)} ·
											{copy.matchedCardsPrefix}: {run.matched_card_count}
										</p>
									</div>
									<Button
										asChild
										variant="link"
										size="sm"
										className="h-auto px-0"
									>
										<Link
											href={`/jobs?job_id=${encodeURIComponent(run.job_id)}`}
										>
											{copy.openJobButton}
										</Link>
									</Button>
								</div>
								<p className="mt-3 text-sm text-muted-foreground">
									{copy.addedTopicsPrefix}:{" "}
									{run.added_topics.join(", ") || copy.noneValue} ·{" "}
									{copy.removedTopicsPrefix}:{" "}
									{run.removed_topics.join(", ") || copy.noneValue}
								</p>
							</div>
						))}
					</CardContent>
				</Card>
			) : null}
		</div>
	);
}
