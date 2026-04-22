import type { Metadata } from "next";
import Link from "next/link";

import { getActionSessionTokenForForm } from "@/app/action-security";
import { getFlashMessage } from "@/app/flash-message";
import { upsertWatchlistAction } from "@/app/watchlists/actions";
import {
	FormCheckboxField,
	FormInputField,
	FormSelectField,
} from "@/components/form-field";
import { SignalStrip } from "@/components/signal-strip";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { WebActionSessionHiddenInput } from "@/components/web-action-session-hidden-input";
import { apiClient } from "@/lib/api/client";
import { formatDateTime } from "@/lib/format";
import { getLocaleMessages } from "@/lib/i18n/messages";
import {
	resolveSearchParams,
	type SearchParamsInput,
} from "@/lib/search-params";
import { buildProductMetadata } from "@/lib/seo";
import type { VendorSignalCatalogResponse } from "@/lib/api/types";

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
		compose,
		name,
		matcher_type: matcherTypeParam,
		matcher_value: matcherValueParam,
		delivery_channel: deliveryChannelParam,
	} = await resolveSearchParams(searchParams, [
		"status",
		"code",
		"watchlist_id",
		"compose",
		"name",
		"matcher_type",
		"matcher_value",
		"delivery_channel",
	] as const);
	const sessionToken = getActionSessionTokenForForm();

	const [watchlistsResult, opsResult, vendorCatalogResult] = await Promise.all([
		apiClient
			.listWatchlists()
			.then((items) => ({ items, error: false }))
			.catch(() => ({ items: [], error: true })),
		apiClient
			.getOpsInbox({ limit: 4, window_hours: 24 })
				.then((payload) => ({ payload, error: false }))
				.catch(() => ({ payload: null, error: true })),
		apiClient
			.listVendorSignalTemplates()
			.then((payload) => ({ payload, error: false }))
			.catch(() => ({
				payload: {
					signal_layers: [],
					vendors: [],
				} satisfies VendorSignalCatalogResponse,
				error: true,
			})),
	]);

	const watchlists = watchlistsResult.items;
	const vendorCatalog = vendorCatalogResult.payload;
	const editingWatchlist = watchlistId.trim()
		? (watchlists.find((item) => item.id === watchlistId.trim()) ?? null)
		: null;
	const starterDefaults = {
		name: name.trim(),
		matcherType: matcherTypeParam.trim() || "topic_key",
		matcherValue: matcherValueParam.trim(),
		deliveryChannel: deliveryChannelParam.trim() || "dashboard",
	};
	const starterVendor = !editingWatchlist
		? vendorCatalog.vendors.find(
				(vendor) =>
					vendor.starter_watchlist.name === starterDefaults.name ||
					(vendor.starter_watchlist.matcher_type === starterDefaults.matcherType &&
						vendor.starter_watchlist.matcher_value === starterDefaults.matcherValue),
			) ?? null
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
	const openCreateWatchlist =
		compose.trim() === "1" ||
		Boolean(editingWatchlist) ||
		Boolean(starterDefaults.name || starterDefaults.matcherValue);
	const compounderFrontDoorHref = trendWatchlist
		? `/trends?watchlist_id=${encodeURIComponent(trendWatchlist.id)}`
		: "/trends";
	const isReadyEmpty = watchlists.length === 0 && !watchlistsResult.error;
	const watchlistSnapshotItems = briefingPageResult.payload
		? [
				{
					label: "Source families",
					value: briefingPageResult.payload.briefing.summary.source_count,
					valueLabel: String(
						briefingPageResult.payload.briefing.summary.source_count,
					),
				},
				{
					label: "Recent runs",
					value: briefingPageResult.payload.briefing.summary.run_count,
					valueLabel: String(
						briefingPageResult.payload.briefing.summary.run_count,
					),
					tone: "success" as const,
				},
				{
					label: "Matched cards",
					value: briefingPageResult.payload.briefing.summary.matched_cards,
					valueLabel: String(
						briefingPageResult.payload.briefing.summary.matched_cards,
					),
				},
			]
		: [];

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

			{isReadyEmpty && !starterVendor ? (
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<CardTitle>{copy.emptyReadyTitle}</CardTitle>
						<CardDescription>{copy.emptyReadyDescription}</CardDescription>
					</CardHeader>
					<CardContent className="flex flex-wrap gap-3">
						<Button asChild variant="hero" size="sm">
							<Link href="/watchlists?compose=1#create-watchlist">
								{copy.emptyReadyButton}
							</Link>
						</Button>
						<Button asChild variant="outline" size="sm">
							<Link href="/feed">Browse feed first</Link>
						</Button>
					</CardContent>
				</Card>
			) : null}

			{trendWatchlist && briefingPageResult.payload ? (
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<CardTitle>Continue this watchlist</CardTitle>
						<CardDescription>
							Start here first. Editing, alerts, and raw movement can wait.
						</CardDescription>
					</CardHeader>
					<CardContent className="space-y-4">
						<div className="rounded-lg border border-border/60 bg-muted/20 p-4">
							<p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
								Current story
							</p>
							<p className="mt-2 font-medium text-foreground">
								{selectedStory?.headline ?? trendWatchlist.name}
							</p>
							<p className="mt-2 text-sm text-muted-foreground">
								{briefingPageResult.payload.briefing.summary.overview}
							</p>
							{briefingPageResult.payload.story_change_summary ? (
								<p className="mt-3 text-sm text-muted-foreground">
									Latest shift:{" "}
									{briefingPageResult.payload.story_change_summary}
								</p>
							) : null}
						</div>

						{watchlistSnapshotItems.length > 0 ? (
							<details className="rounded-xl border border-border/60 bg-background/55 p-4">
								<summary className="cursor-pointer text-sm font-medium text-foreground">
									Story signals later
								</summary>
								<div className="mt-3">
									<SignalStrip
										title="Watchlist snapshot"
										description="Open this only after you decide this is the story you want to keep following."
										items={watchlistSnapshotItems}
									/>
								</div>
							</details>
						) : null}

						<div className="flex flex-wrap gap-3">
							<Button asChild variant="hero" size="sm">
								<Link href={compounderFrontDoorHref}>Open story</Link>
							</Button>
							{selectedStoryRoutes?.briefing ? (
								<Link
									href={selectedStoryRoutes.briefing}
									className="inline-flex items-center text-sm text-muted-foreground underline underline-offset-4 hover:text-foreground"
								>
									Open briefing story
								</Link>
							) : null}
							{briefingPageResult.payload.ask_route ? (
								<Link
									href={briefingPageResult.payload.ask_route}
									className="inline-flex items-center text-sm text-muted-foreground underline underline-offset-4 hover:text-foreground"
								>
									Ask about this story
								</Link>
							) : null}
						</div>
					</CardContent>
				</Card>
			) : null}

			<section className="grid gap-4 lg:grid-cols-[1.15fr_1fr]">
				{!isReadyEmpty || watchlistsResult.error ? (
					<details
						className="group rounded-xl border border-border/70 bg-card text-card-foreground folo-surface"
						open={openCreateWatchlist}
					>
						<summary className="flex cursor-pointer list-none items-start justify-between gap-4 px-6 py-6 marker:content-none [&::-webkit-details-marker]:hidden">
							<div className="space-y-1">
								<p className="text-lg font-semibold text-foreground">
									Saved watchlists
								</p>
								<p className="text-sm text-muted-foreground">
									Open the topic you already know. Create or configure later.
								</p>
							</div>
							<span className="rounded-full border border-border/60 bg-background/70 px-3 py-1 text-xs font-medium text-muted-foreground transition group-open:text-foreground">
								{editingWatchlist ? "Open" : "Later"}
							</span>
						</summary>
						<div className="border-t border-border/50 px-6 pb-6 pt-4">
							{watchlistsResult.error ? (
								<p className="text-sm text-muted-foreground">
									{copy.currentError}
								</p>
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
														·{" "}
														{item.enabled
															? copy.enabledState
															: copy.pausedState}
													</p>
													<p className="text-xs text-muted-foreground">
														{copy.updatedPrefix}:{" "}
														{formatDateTime(item.updated_at)}
													</p>
												</div>
												<div className="flex flex-wrap gap-3">
													<Button asChild variant="outline" size="sm">
														<Link
															href={`/trends?watchlist_id=${encodeURIComponent(item.id)}`}
														>
															Open story
														</Link>
													</Button>
													<Button asChild variant="outline" size="sm">
														<Link
															href={`/watchlists?watchlist_id=${encodeURIComponent(item.id)}`}
														>
															{copy.editButton}
														</Link>
													</Button>
												</div>
											</div>
										</li>
									))}
								</ul>
							)}
						</div>
					</details>
				) : null}

				<div className="space-y-4">
					{starterVendor ? (
						<Card className="folo-surface border-primary/25 bg-primary/5">
							<CardHeader>
								<CardTitle>Continue with {starterVendor.label}</CardTitle>
								<CardDescription>
									Step 2 of 3. Name the watchlist, confirm the matcher, then
									use briefings to read the current story, the recent changes,
									and the receipts together.
								</CardDescription>
							</CardHeader>
							<CardContent className="space-y-3">
								<div className="flex flex-wrap items-center gap-2">
									<Badge variant="outline">Starter watchlist</Badge>
									<Badge variant="outline">
										{starterVendor.starter_watchlist.matcher_value}
									</Badge>
								</div>
								<p className="text-sm text-muted-foreground">
									{starterVendor.starter_watchlist.briefing_goal}
								</p>
								<div className="flex flex-wrap gap-3">
									<Button asChild variant="outline" size="sm">
										<Link href="/subscriptions#vendor-sources">
											Back to vendor sources
										</Link>
									</Button>
									<Button asChild variant="outline" size="sm">
										<Link href="/briefings">See the payoff later</Link>
									</Button>
								</div>
							</CardContent>
						</Card>
					) : null}

					{vendorCatalog.vendors.length > 0 && !starterVendor ? (
						<Card className="folo-surface border-border/70">
							<CardHeader>
								<CardTitle>Vendor starters</CardTitle>
								<CardDescription>
									Start from the vendor you already care about. Keep the
									briefing goal and signal mix visible, then tune matching later.
								</CardDescription>
							</CardHeader>
							<CardContent className="grid gap-3">
								{vendorCatalog.vendors.map((vendor) => (
									<div
										key={vendor.id}
										className="rounded-lg border border-border/60 bg-muted/20 p-4"
									>
										<div className="space-y-2">
											<div className="flex flex-wrap items-center gap-2">
												<p className="font-medium text-foreground">
													{vendor.label}
												</p>
												<Badge variant="outline">
													{vendor.starter_watchlist.matcher_value}
												</Badge>
											</div>
											<p className="text-sm text-muted-foreground">
												{vendor.starter_watchlist.briefing_goal}
											</p>
											<p className="text-sm text-muted-foreground">
												{vendor.official_first_move}
											</p>
										</div>
										<div className="mt-3 flex flex-wrap gap-3">
											<Button asChild variant="hero" size="sm">
												<Link
													href={`/watchlists?compose=1&name=${encodeURIComponent(vendor.starter_watchlist.name)}&matcher_type=${encodeURIComponent(vendor.starter_watchlist.matcher_type)}&matcher_value=${encodeURIComponent(vendor.starter_watchlist.matcher_value)}&delivery_channel=${encodeURIComponent(vendor.starter_watchlist.delivery_channel)}#create-watchlist`}
												>
													Create starter watchlist
												</Link>
											</Button>
											<Button asChild variant="outline" size="sm">
												<Link href={`/subscriptions#vendor-sources`}>
													Open vendor sources
												</Link>
											</Button>
										</div>
									</div>
								))}
							</CardContent>
						</Card>
					) : null}

					<details
						className="group rounded-xl border border-border/70 bg-card text-card-foreground folo-surface"
						id="create-watchlist"
						open={openCreateWatchlist || isReadyEmpty || Boolean(editingWatchlist)}
					>
						<summary className="flex cursor-pointer list-none items-start justify-between gap-4 px-6 py-6 marker:content-none [&::-webkit-details-marker]:hidden">
							<div className="space-y-1">
								<p className="text-lg font-semibold text-foreground">
									{editingWatchlist ? "Edit this watchlist" : copy.saveTitle}
								</p>
								<p className="text-sm text-muted-foreground">
									{starterVendor
										? `Finish the ${starterVendor.label} starter here, then read the first briefing.`
										: "Start with one topic or source. Delivery can wait."}
								</p>
							</div>
							<span className="rounded-full border border-border/60 bg-background/70 px-3 py-1 text-xs font-medium text-muted-foreground transition group-open:text-foreground">
								{openCreateWatchlist || isReadyEmpty || editingWatchlist
									? "Open"
									: "Later"}
							</span>
						</summary>
						<div className="border-t border-border/50 px-6 pb-6 pt-4">
							{starterVendor ? (
								<div className="mb-4 rounded-xl border border-border/60 bg-background/70 p-4">
									<p className="text-sm font-medium text-foreground">
										You are creating {starterVendor.starter_watchlist.name}
									</p>
									<p className="mt-1 text-sm text-muted-foreground">
										Keep the starter matcher for now. You can widen delivery and
										matching details later.
									</p>
								</div>
							) : null}
							<form action={upsertWatchlistAction} className="grid gap-4">
								<WebActionSessionHiddenInput sessionToken={sessionToken} />
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
									defaultValue={editingWatchlist?.name ?? starterDefaults.name}
									placeholder={copy.namePlaceholder}
									required
								/>
								{editingWatchlist ? (
									<FormSelectField
										name="matcher_type"
										label={copy.watchTypeLabel}
										defaultValue={editingWatchlist.matcher_type}
										options={matcherOptions}
									/>
								) : (
									<input
										type="hidden"
										name="matcher_type"
										value={starterDefaults.matcherType}
										readOnly
									/>
								)}
								<FormInputField
									id="watchlist-value"
									name="matcher_value"
									label={
										editingWatchlist
											? copy.matcherValueLabel
											: "What do you want to keep following?"
									}
									type="text"
									defaultValue={
										editingWatchlist?.matcher_value ?? starterDefaults.matcherValue
									}
									placeholder={copy.matcherValuePlaceholder}
									required
								/>
								<details
									className="rounded-xl border border-border/60 bg-background/55 p-4"
									open={Boolean(editingWatchlist)}
								>
									<summary className="cursor-pointer text-sm font-medium text-foreground">
										{editingWatchlist
											? "Delivery and matching details"
											: "Delivery later"}
									</summary>
									<div className="mt-4 grid gap-4">
										{!editingWatchlist ? (
											<>
												<p className="text-sm text-muted-foreground">
													Start with the topic first. Tighten the matching rule
													and delivery only after this watchlist proves useful.
												</p>
												<FormSelectField
													name="matcher_type"
													label={copy.watchTypeLabel}
													defaultValue={starterDefaults.matcherType}
													options={matcherOptions}
												/>
											</>
										) : null}
										<FormSelectField
											name="delivery_channel"
											label={copy.deliveryLabel}
											defaultValue={
												editingWatchlist?.delivery_channel ??
												starterDefaults.deliveryChannel
											}
											options={deliveryOptions}
										/>
										<FormCheckboxField
											name="enabled"
											label={copy.enabledLabel}
											defaultChecked={editingWatchlist?.enabled ?? true}
										/>
									</div>
								</details>
								<div className="flex flex-wrap gap-3">
									<Button type="submit" variant="hero" size="sm">
										{editingWatchlist ? copy.updateButton : copy.saveButton}
									</Button>
									{editingWatchlist ? (
										<>
											<Button asChild variant="outline" size="sm">
												<Link href="/watchlists">{copy.createNewButton}</Link>
											</Button>
											<Button asChild variant="outline" size="sm">
												<Link
													href={`/trends?watchlist_id=${encodeURIComponent(editingWatchlist.id)}`}
												>
													{copy.openTrendViewButton}
												</Link>
											</Button>
										</>
									) : null}
								</div>
							</form>
						</div>
					</details>

					<details className="group rounded-xl border border-border/70 bg-card text-card-foreground folo-surface">
						<summary className="flex cursor-pointer list-none items-start justify-between gap-4 px-6 py-6 marker:content-none [&::-webkit-details-marker]:hidden">
							<div className="space-y-1">
								<p className="text-lg font-semibold text-foreground">
									{copy.alertTitle}
								</p>
								<p className="text-sm text-muted-foreground">
									Keep this secondary until it is actually ready.
								</p>
							</div>
							<span className="rounded-full border border-border/60 bg-background/70 px-3 py-1 text-xs font-medium text-muted-foreground transition group-open:text-foreground">
								Later
							</span>
						</summary>
						<div className="border-t border-border/50 px-6 pb-6 pt-4">
							<div className="space-y-3 text-sm text-muted-foreground">
								<p>{copy.alertDescription}</p>
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
							</div>
						</div>
					</details>
				</div>
			</section>

			{trendWatchlist && trendResult.payload ? (
				<details className="group rounded-xl border border-border/70 bg-card text-card-foreground folo-surface">
					<summary className="flex cursor-pointer list-none items-start justify-between gap-4 px-6 py-6 marker:content-none [&::-webkit-details-marker]:hidden">
						<div className="space-y-1">
							<p className="text-lg font-semibold text-foreground">
								{copy.recentMovementTitle}
							</p>
							<p className="text-sm text-muted-foreground">
								{copy.recentMovementDescription}
							</p>
						</div>
						<span className="rounded-full border border-border/60 bg-background/70 px-3 py-1 text-xs font-medium text-muted-foreground transition group-open:text-foreground">
							Later
						</span>
					</summary>
					<div className="border-t border-border/50 px-6 pb-6 pt-4">
						<div className="space-y-4">
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
						</div>
					</div>
				</details>
			) : null}
		</div>
	);
}
