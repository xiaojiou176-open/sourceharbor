import type { Metadata } from "next";
import Link from "next/link";

import { getActionSessionTokenForForm } from "@/app/action-security";
import { pollIngestAction, processVideoAction } from "@/app/actions";
import { getFlashMessage } from "@/app/flash-message";
import { toDisplayStatus } from "@/app/status";
import {
	FormCheckboxField,
	FormInputField,
	FormSelectField,
} from "@/components/form-field";
import { mapStatusCssToTone, StatusBadge } from "@/components/status-badge";
import { SubmitButton } from "@/components/submit-button";
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
import { getLocaleMessages } from "@/lib/i18n/messages";
import {
	resolveSearchParams,
	type SearchParamsInput,
} from "@/lib/search-params";
import { buildProductMetadata } from "@/lib/seo";

const dashboardCopy = getLocaleMessages().dashboard;

export const metadata: Metadata = buildProductMetadata({
	title: dashboardCopy.metadataTitle,
	description: dashboardCopy.metadataDescription,
	route: "dashboard",
});

type DashboardPageProps = {
	searchParams?: SearchParamsInput;
};

const POLL_PLATFORM_OPTIONS = [
	{ value: "", label: "All" },
	{ value: "youtube", label: "YouTube" },
	{ value: "bilibili", label: "Bilibili" },
];

const PROCESS_PLATFORM_OPTIONS = [
	{ value: "youtube", label: "YouTube" },
	{ value: "bilibili", label: "Bilibili" },
];

const PROCESS_MODE_OPTIONS = [
	{ value: "full", label: "Full run" },
	{ value: "text_only", label: "Text only" },
	{ value: "refresh_comments", label: "Refresh comments" },
	{ value: "refresh_llm", label: "Refresh LLM outputs" },
];

const BUILDER_RESOURCE_LINKS = {
	builders: "/builders",
	distribution:
		"https://github.com/xiaojiou176-open/sourceharbor/blob/main/docs/public-distribution.md",
	starterPacks:
		"https://github.com/xiaojiou176-open/sourceharbor/blob/main/starter-packs/README.md",
	cli: "https://github.com/xiaojiou176-open/sourceharbor/blob/main/packages/sourceharbor-cli/README.md",
	sdk: "https://github.com/xiaojiou176-open/sourceharbor/blob/main/packages/sourceharbor-sdk/README.md",
	mediaKit:
		"https://github.com/xiaojiou176-open/sourceharbor/blob/main/docs/media-kit.md",
} as const;

const OFFICIAL_SURFACE_SNAPSHOTS = [
	{
		name: "Codex",
		status: "Bundle ready, listing still unavailable",
		detail:
			"Compatible bundle exists today; official directory listing still is not self-serve.",
	},
	{
		name: "Claude Code",
		status: "Submission ready, review still pending",
		detail:
			"Bundle is ready now, but live listing still needs marketplace submit and review proof.",
	},
	{
		name: "OpenClaw / ClawHub",
		status: "Template ready, publish receipt still missing",
		detail:
			"Local pack and package template exist, but a real public publish receipt is still missing.",
	},
	{
		name: "Official MCP Registry",
		status: "Metadata ready, install proof still missing",
		detail:
			"Registry-shaped metadata exists, but live registry publication still needs install-artifact and namespace proof.",
	},
] as const;

const FIRST_HOP_DOC_LINKS = {
	seeItFast:
		"https://github.com/xiaojiou176-open/sourceharbor/blob/main/docs/see-it-fast.md",
	startHere:
		"https://github.com/xiaojiou176-open/sourceharbor/blob/main/docs/start-here.md",
	publicDistribution:
		"https://github.com/xiaojiou176-open/sourceharbor/blob/main/docs/public-distribution.md",
} as const;

function renderAlert(status: string, code: string) {
	if (!status || !code) {
		return null;
	}
	const isError = status === "error";
	if (isError) {
		return (
			<p className="alert alert-enter error" role="alert" aria-live="assertive">
				{getFlashMessage(code)}
			</p>
		);
	}
	return (
		<output
			className="alert alert-enter success"
			aria-live="polite"
			aria-atomic="true"
		>
			{getFlashMessage(code)}
		</output>
	);
}

function renderMetricValue(value: number, unavailableText?: string) {
	return (
		<div className="text-3xl font-semibold">
			{unavailableText ? (
				<>
					<span aria-hidden="true">--</span>
					<span className="sr-only">{unavailableText}</span>
				</>
			) : (
				value
			)}
		</div>
	);
}

function toPlatformLabel(platform: string): string {
	const normalized = platform.trim().toLowerCase();
	if (normalized === "youtube") {
		return "YouTube";
	}
	if (normalized === "bilibili") {
		return "Bilibili";
	}
	return platform;
}

function DashboardStatusBadge({ status }: { status: string | null }) {
	const normalized = status ?? "idle";
	const statusDisplay = toDisplayStatus(normalized);
	return (
		<StatusBadge
			label={statusDisplay.label}
			tone={mapStatusCssToTone(statusDisplay.css)}
		/>
	);
}

export default async function DashboardPage({
	searchParams,
}: DashboardPageProps) {
	const messages = getLocaleMessages();
	const copy = messages.dashboard;
	const builderCopy = messages.builderSurfaces;
	const builderCards = [
		builderCopy.cards.reuse,
		builderCopy.cards.proof,
		builderCopy.cards.compounders,
	];
	const whyNowCards = [
		{
			title: copy.whyNow.sharedTruthTitle,
			description: copy.whyNow.sharedTruthDescription,
		},
		{
			title: copy.whyNow.proofFirstTitle,
			description: copy.whyNow.proofFirstDescription,
		},
		{
			title: copy.whyNow.returnLoopTitle,
			description: copy.whyNow.returnLoopDescription,
		},
	];
	const builderResourceLinks = [
		{
			href: BUILDER_RESOURCE_LINKS.builders,
			label: builderCopy.buildersGuideCta,
		},
		{
			href: BUILDER_RESOURCE_LINKS.distribution,
			label: "Open distribution ledger",
		},
		{
			href: BUILDER_RESOURCE_LINKS.starterPacks,
			label: builderCopy.starterPacksCta,
		},
		{
			href: BUILDER_RESOURCE_LINKS.cli,
			label: builderCopy.cliPackageCta,
		},
		{
			href: BUILDER_RESOURCE_LINKS.sdk,
			label: builderCopy.sdkPackageCta,
		},
		{
			href: BUILDER_RESOURCE_LINKS.mediaKit,
			label: "Open media kit",
		},
	];
	const { status, code } = await resolveSearchParams(searchParams, [
		"status",
		"code",
	] as const);
	const sessionToken = getActionSessionTokenForForm();

	const [subscriptionsResult, videosResult, ingestRunsResult] =
		await Promise.all([
			apiClient
				.listSubscriptions()
				.then((data) => ({ data, errorCode: null as string | null }))
				.catch(() => ({
					data: [] as Awaited<ReturnType<typeof apiClient.listSubscriptions>>,
					errorCode: "ERR_REQUEST_FAILED",
				})),
			apiClient
				.listVideos({ limit: 200 })
				.then((data) => ({ data, errorCode: null as string | null }))
				.catch(() => ({
					data: [] as Awaited<ReturnType<typeof apiClient.listVideos>>,
					errorCode: "ERR_REQUEST_FAILED",
				})),
			apiClient
				.listIngestRuns({ limit: 5 })
				.then((data) => ({ data, errorCode: null as string | null }))
				.catch(() => ({
					data: [] as Awaited<ReturnType<typeof apiClient.listIngestRuns>>,
					errorCode: "ERR_REQUEST_FAILED",
				})),
		]);

	const subscriptions = subscriptionsResult.data;
	const videos = videosResult.data;
	const ingestRuns = ingestRunsResult.data;
	const loadErrorCode = subscriptionsResult.errorCode ?? videosResult.errorCode;
	const subscriptionsUnavailable = subscriptionsResult.errorCode !== null;
	const videosUnavailable = videosResult.errorCode !== null;
	const ingestRunsUnavailable = ingestRunsResult.errorCode !== null;
	const runningJobs = videos.filter(
		(video) => video.status === "running" || video.status === "queued",
	).length;
	const failedJobs = videos.filter((video) => video.status === "failed").length;

	return (
		<div className="folo-page-shell folo-unified-shell">
			<div className="folo-page-header">
				<p className="folo-page-kicker">{copy.kicker}</p>
				<h1 className="folo-page-title" data-route-heading>
					{copy.heroTitle}
				</h1>
				<p className="folo-page-subtitle">{copy.heroSubtitle}</p>
			</div>

			{renderAlert(status, code)}
			{loadErrorCode ? (
				<Card
					className="folo-surface border-destructive/40 bg-destructive/5"
					role="alert"
					aria-live="assertive"
				>
					<CardHeader className="gap-2">
						<CardTitle className="text-base">{copy.loadErrorTitle}</CardTitle>
						<CardDescription>{getFlashMessage(loadErrorCode)}</CardDescription>
					</CardHeader>
					<CardContent className="pt-0">
						<Button asChild variant="outline" size="sm">
							<Link href="/">{copy.retryCurrentPage}</Link>
						</Button>
					</CardContent>
				</Card>
			) : null}

			<section
				className="grid gap-4 xl:grid-cols-3"
				aria-label="Why builders keep reading"
			>
				<h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-muted-foreground xl:col-span-3">
					{copy.sectionHeadings.whyNow}
				</h2>
				{whyNowCards.map((card) => (
					<Card key={card.title} className="folo-surface border-border/70">
						<CardHeader>
							<CardTitle>{card.title}</CardTitle>
							<CardDescription>{card.description}</CardDescription>
						</CardHeader>
					</Card>
				))}
			</section>

			<section
				className="grid gap-4 xl:grid-cols-3"
				aria-label="Choose your first SourceHarbor path"
			>
				<h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-muted-foreground xl:col-span-3">
					{copy.sectionHeadings.firstHop}
				</h2>
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<CardTitle>{copy.firstHop.evaluateTitle}</CardTitle>
						<CardDescription>
							{copy.firstHop.evaluateDescription}
						</CardDescription>
					</CardHeader>
					<CardContent className="flex flex-wrap items-center gap-3 pt-0">
						<Button asChild>
							<a
								href={FIRST_HOP_DOC_LINKS.seeItFast}
								target="_blank"
								rel="noreferrer"
							>
								{copy.firstHop.evaluatePrimaryCta}
							</a>
						</Button>
						<Button asChild variant="outline">
							<Link href="/proof">{copy.firstHop.evaluateSecondaryCta}</Link>
						</Button>
					</CardContent>
				</Card>
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<CardTitle>{copy.firstHop.operateTitle}</CardTitle>
						<CardDescription>
							{copy.firstHop.operateDescription}
						</CardDescription>
					</CardHeader>
					<CardContent className="flex flex-wrap items-center gap-3 pt-0">
						<Button asChild>
							<a
								href={FIRST_HOP_DOC_LINKS.startHere}
								target="_blank"
								rel="noreferrer"
							>
								{copy.firstHop.operatePrimaryCta}
							</a>
						</Button>
						<Button asChild variant="outline">
							<Link href="/subscriptions">
								{copy.firstHop.operateSecondaryCta}
							</Link>
						</Button>
						<Button asChild variant="outline">
							<Link href="/ops">{copy.firstHop.operateTertiaryCta}</Link>
						</Button>
					</CardContent>
				</Card>
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<CardTitle>{copy.firstHop.buildTitle}</CardTitle>
						<CardDescription>{copy.firstHop.buildDescription}</CardDescription>
					</CardHeader>
					<CardContent className="flex flex-wrap items-center gap-3 pt-0">
						<Button asChild>
							<Link href="/mcp">{copy.firstHop.buildPrimaryCta}</Link>
						</Button>
						<Button asChild variant="outline">
							<Link href="/builders">{copy.firstHop.buildSecondaryCta}</Link>
						</Button>
						<Button asChild variant="outline">
							<a
								href={FIRST_HOP_DOC_LINKS.publicDistribution}
								target="_blank"
								rel="noreferrer"
							>
								{copy.firstHop.buildTertiaryCta}
							</a>
						</Button>
					</CardContent>
				</Card>
			</section>

			<section
				className="grid gap-4 xl:grid-cols-4"
				aria-label="SourceHarbor front doors"
			>
				<h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-muted-foreground xl:col-span-4">
					{copy.sectionHeadings.primaryFrontDoors}
				</h2>
				<Card className="folo-surface border-border/70 xl:col-span-1">
					<CardHeader>
						<CardTitle>{copy.frontDoors.subscriptionsTitle}</CardTitle>
						<CardDescription>
							{copy.frontDoors.subscriptionsDescription}
						</CardDescription>
					</CardHeader>
					<CardContent className="space-y-3 pt-0">
						<div className="flex flex-wrap items-center gap-3">
							<Button asChild>
								<Link href="/subscriptions">
									{copy.frontDoors.subscriptionsCta}
								</Link>
							</Button>
							<Button asChild variant="outline">
								<Link href="/trends">{copy.compounders.trendsCta}</Link>
							</Button>
						</div>
						<p className="text-sm text-muted-foreground">
							{copy.frontDoors.subscriptionsHint}
						</p>
					</CardContent>
				</Card>
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<CardTitle>{copy.frontDoors.searchTitle}</CardTitle>
						<CardDescription>
							{copy.frontDoors.searchDescription}
						</CardDescription>
					</CardHeader>
					<CardContent className="flex flex-wrap items-center gap-3 pt-0">
						<Button asChild>
							<Link href="/search">{copy.frontDoors.searchCta}</Link>
						</Button>
						<Button asChild variant="outline">
							<Link href="/knowledge">{copy.frontDoors.knowledgeCta}</Link>
						</Button>
					</CardContent>
				</Card>
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<CardTitle>{copy.frontDoors.askTitle}</CardTitle>
						<CardDescription>{copy.frontDoors.askDescription}</CardDescription>
					</CardHeader>
					<CardContent className="flex flex-wrap items-center gap-3 pt-0">
						<Button asChild>
							<Link href="/ask">{copy.frontDoors.askCta}</Link>
						</Button>
						<Button asChild variant="outline">
							<Link href="/briefings">{copy.frontDoors.briefingsCta}</Link>
						</Button>
						<p className="text-sm text-muted-foreground">
							{copy.frontDoors.askHint}
						</p>
					</CardContent>
				</Card>
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<CardTitle>{copy.frontDoors.mcpTitle}</CardTitle>
						<CardDescription>{copy.frontDoors.mcpDescription}</CardDescription>
					</CardHeader>
					<CardContent className="flex flex-wrap items-center gap-3 pt-0">
						<Button asChild>
							<Link href="/mcp">{copy.frontDoors.mcpCta}</Link>
						</Button>
						<Button asChild variant="outline">
							<Link href="/jobs">{copy.frontDoors.jobCta}</Link>
						</Button>
					</CardContent>
				</Card>
			</section>

			<section aria-label="SourceHarbor builder entry points">
				<h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-muted-foreground">
					{copy.sectionHeadings.builderEntryPoints}
				</h2>
				<div className="grid gap-4 xl:grid-cols-[minmax(0,1.45fr)_minmax(0,1fr)]">
					<Card className="folo-surface border-primary/20 bg-gradient-to-br from-primary/10 via-background to-background">
						<CardHeader className="gap-3">
							<CardTitle>{builderCopy.title}</CardTitle>
							<CardDescription>{builderCopy.subtitle}</CardDescription>
						</CardHeader>
						<CardContent className="space-y-4 pt-0">
							<div className="flex flex-wrap gap-2">
								{builderCopy.highlightPills.map((pill) => (
									<Badge
										key={pill}
										variant="outline"
										className="border-primary/20"
									>
										{pill}
									</Badge>
								))}
							</div>
							<div className="flex flex-wrap items-center gap-3">
								<Button asChild variant="hero">
									<Link href="/mcp">{builderCopy.mcpCta}</Link>
								</Button>
								<Button asChild variant="outline">
									<Link href="/use-cases/codex">{builderCopy.codexCta}</Link>
								</Button>
								<Button asChild variant="outline">
									<Link href="/use-cases/claude-code">
										{builderCopy.claudeCodeCta}
									</Link>
								</Button>
								<Button asChild variant="outline">
									<Link href="/proof">{builderCopy.proofCta}</Link>
								</Button>
								<Button asChild variant="outline">
									<Link href="/use-cases/research-pipeline">
										{builderCopy.researchCta}
									</Link>
								</Button>
							</div>
							<div className="space-y-3 rounded-xl border border-border/60 bg-background/80 p-4">
								<div className="space-y-1">
									<p className="text-sm font-medium text-foreground">
										{builderCopy.resourceTitle}
									</p>
									<p className="text-sm text-muted-foreground">
										{builderCopy.resourceDescription}
									</p>
								</div>
								<div className="flex flex-wrap gap-2">
									{builderResourceLinks.map((link) => (
										<Button key={link.href} asChild variant="outline" size="sm">
											{link.href.startsWith("http") ? (
												<a href={link.href} target="_blank" rel="noreferrer">
													{link.label}
												</a>
											) : (
												<Link href={link.href}>{link.label}</Link>
											)}
										</Button>
									))}
								</div>
							</div>
							<div className="space-y-3 rounded-xl border border-border/60 bg-background/80 p-4">
								<div className="space-y-1">
									<p className="text-sm font-medium text-foreground">
										Official-surface status
									</p>
									<p className="text-sm text-muted-foreground">
										Use this quick board when you want the one-minute answer to
										&quot;what already exists&quot; versus &quot;what still
										needs a real submit or read-back proof&quot;.
									</p>
								</div>
								<ul className="space-y-2 text-sm text-muted-foreground">
									{OFFICIAL_SURFACE_SNAPSHOTS.map((item) => (
										<li
											key={item.name}
											className="rounded-lg border border-border/60 bg-muted/20 px-3 py-2"
										>
											<p className="font-medium text-foreground">{item.name}</p>
											<p>{item.status}</p>
											<p className="mt-1">{item.detail}</p>
										</li>
									))}
								</ul>
								<div className="flex flex-wrap gap-2">
									<Button asChild variant="outline" size="sm">
										<Link href="/builders">Open builders guide</Link>
									</Button>
									<Button asChild variant="outline" size="sm">
										<a
											href={BUILDER_RESOURCE_LINKS.distribution}
											target="_blank"
											rel="noreferrer"
										>
											Open distribution ledger
										</a>
									</Button>
								</div>
							</div>
						</CardContent>
					</Card>

					<div className="grid gap-4">
						{builderCards.map((card) => (
							<Card key={card.title} className="folo-surface border-border/70">
								<CardHeader>
									<CardTitle>{card.title}</CardTitle>
									<CardDescription>{card.description}</CardDescription>
								</CardHeader>
								<CardContent className="flex flex-wrap gap-2 pt-0">
									{card.bullets.map((bullet) => (
										<Badge key={bullet} variant="secondary">
											{bullet}
										</Badge>
									))}
								</CardContent>
							</Card>
						))}
					</div>
				</div>
			</section>

			<section
				className="grid gap-4 xl:grid-cols-4"
				aria-label="SourceHarbor compounder surfaces"
			>
				<h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-muted-foreground xl:col-span-4">
					{copy.sectionHeadings.compounderSurfaces}
				</h2>
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<CardTitle>{copy.compounders.watchlistsTitle}</CardTitle>
						<CardDescription>
							{copy.compounders.watchlistsDescription}
						</CardDescription>
					</CardHeader>
					<CardContent className="flex flex-wrap items-center gap-3 pt-0">
						<Button asChild>
							<Link href="/watchlists">{copy.compounders.watchlistsCta}</Link>
						</Button>
						<Button asChild variant="outline">
							<Link href="/trends">{copy.compounders.trendsCta}</Link>
						</Button>
					</CardContent>
				</Card>
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<CardTitle>{copy.compounders.trendsTitle}</CardTitle>
						<CardDescription>
							{copy.compounders.trendsDescription}
						</CardDescription>
					</CardHeader>
					<CardContent className="flex flex-wrap items-center gap-3 pt-0">
						<Button asChild>
							<Link href="/trends">{copy.compounders.trendsCta}</Link>
						</Button>
						<Button asChild variant="outline">
							<Link href="/briefings">{copy.compounders.briefingsCta}</Link>
						</Button>
					</CardContent>
				</Card>
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<CardTitle>{copy.compounders.briefingsTitle}</CardTitle>
						<CardDescription>
							{copy.compounders.briefingsDescription}
						</CardDescription>
					</CardHeader>
					<CardContent className="flex flex-wrap items-center gap-3 pt-0">
						<Button asChild>
							<Link href="/briefings">{copy.compounders.briefingsCta}</Link>
						</Button>
						<Button asChild variant="outline">
							<Link href="/ask">{copy.frontDoors.askCta}</Link>
						</Button>
					</CardContent>
				</Card>
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<CardTitle>{copy.compounders.playgroundTitle}</CardTitle>
						<CardDescription>
							{copy.compounders.playgroundDescription}
						</CardDescription>
					</CardHeader>
					<CardContent className="flex flex-wrap items-center gap-3 pt-0">
						<Button asChild>
							<Link href="/playground">{copy.compounders.playgroundCta}</Link>
						</Button>
						<Button asChild variant="outline">
							<Link href="/proof">{copy.compounders.proofCta}</Link>
						</Button>
					</CardContent>
				</Card>
			</section>

			<section
				className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
				aria-label={copy.metricsRegionLabel}
			>
				<h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-muted-foreground sm:col-span-2 xl:col-span-4">
					{copy.sectionHeadings.keyMetrics}
				</h2>
				<Card className="folo-surface overflow-hidden border-border/70">
					<CardHeader className="gap-2">
						<CardDescription>
							{copy.metrics.subscriptions.title}
						</CardDescription>
						{renderMetricValue(
							subscriptions.length,
							subscriptionsUnavailable
								? copy.metrics.subscriptions.unavailable
								: undefined,
						)}
					</CardHeader>
					<CardContent className="space-y-2 pt-0">
						{subscriptionsUnavailable ? (
							<output
								className="text-sm text-muted-foreground"
								aria-live="polite"
								aria-atomic="true"
							>
								{copy.metrics.unavailableOutput}
							</output>
						) : null}
						{subscriptions.length === 0 && !subscriptionsUnavailable ? (
							<Button asChild variant="link" size="sm" className="h-auto px-0">
								<Link href="/subscriptions">
									{copy.metrics.subscriptions.emptyCta}
								</Link>
							</Button>
						) : null}
					</CardContent>
				</Card>
				<Card className="folo-surface overflow-hidden border-border/70">
					<CardHeader className="gap-2">
						<CardDescription>
							{copy.metrics.discoveredVideos.title}
						</CardDescription>
						{renderMetricValue(
							videos.length,
							videosUnavailable
								? copy.metrics.discoveredVideos.unavailable
								: undefined,
						)}
					</CardHeader>
					<CardContent className="pt-0">
						{videosUnavailable ? (
							<output
								className="text-sm text-muted-foreground"
								aria-live="polite"
								aria-atomic="true"
							>
								{copy.metrics.unavailableOutput}
							</output>
						) : null}
					</CardContent>
				</Card>
				<Card
					className={
						!videosUnavailable && runningJobs > 0
							? "folo-surface overflow-hidden border-amber-300/70 bg-amber-50/40 dark:border-amber-900 dark:bg-amber-950/15"
							: "folo-surface overflow-hidden border-border/70"
					}
				>
					<CardHeader className="gap-2">
						<CardDescription>{copy.metrics.runningJobs.title}</CardDescription>
						{renderMetricValue(
							runningJobs,
							videosUnavailable
								? copy.metrics.runningJobs.unavailable
								: undefined,
						)}
					</CardHeader>
					<CardContent className="pt-0">
						{videosUnavailable ? (
							<output
								className="text-sm text-muted-foreground"
								aria-live="polite"
								aria-atomic="true"
							>
								{copy.metrics.unavailableOutput}
							</output>
						) : null}
					</CardContent>
				</Card>
				<Card
					className={
						!videosUnavailable && failedJobs > 0
							? "folo-surface overflow-hidden border-destructive/40 bg-destructive/5"
							: "folo-surface overflow-hidden border-border/70"
					}
				>
					<CardHeader className="gap-2">
						<CardDescription>{copy.metrics.failedJobs.title}</CardDescription>
						{renderMetricValue(
							failedJobs,
							videosUnavailable
								? copy.metrics.failedJobs.unavailable
								: undefined,
						)}
					</CardHeader>
					<CardContent className="space-y-2 pt-0">
						{videosUnavailable ? (
							<output
								className="text-sm text-muted-foreground"
								aria-live="polite"
								aria-atomic="true"
							>
								{copy.metrics.unavailableOutput}
							</output>
						) : null}
						{!videosUnavailable && failedJobs > 0 ? (
							<div className="flex flex-wrap items-center gap-3">
								<Button
									asChild
									variant="link"
									size="sm"
									className="h-auto px-0"
								>
									<Link href="/jobs">{copy.metrics.failedJobs.openFailed}</Link>
								</Button>
								<Button
									asChild
									variant="link"
									size="sm"
									className="h-auto px-0"
								>
									<Link href="/ops">{copy.metrics.failedJobs.openOps}</Link>
								</Button>
							</div>
						) : null}
					</CardContent>
				</Card>
			</section>

			<section className="grid gap-4 lg:grid-cols-2">
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<h2 className="text-xl font-semibold">{copy.pollIngest.title}</h2>
						<CardDescription id="poll-ingest-help">
							{copy.pollIngest.description}
						</CardDescription>
					</CardHeader>
					<CardContent>
						<form action={pollIngestAction} className="grid gap-4">
							<input
								type="hidden"
								name="session_token"
								value={sessionToken}
								suppressHydrationWarning
							/>
							<FormSelectField
								id="poll-platform"
								label={copy.pollIngest.platformLabel}
								name="platform"
								defaultValue=""
								options={POLL_PLATFORM_OPTIONS}
							/>
							<FormInputField
								id="poll-max-new-videos"
								label={copy.pollIngest.maxNewVideosLabel}
								name="max_new_videos"
								type="number"
								min={1}
								max={500}
								defaultValue={50}
							/>
							<div className="flex flex-wrap items-center gap-3">
								<SubmitButton
									pendingLabel={copy.pollIngest.submitPending}
									statusText={copy.pollIngest.submitStatus}
								>
									{copy.pollIngest.submit}
								</SubmitButton>
								<Button asChild variant="outline" size="sm">
									<Link href="/jobs">{copy.pollIngest.queueLink}</Link>
								</Button>
							</div>
						</form>
					</CardContent>
				</Card>

				<Card className="folo-surface border-border/70">
					<CardHeader>
						<h2 className="text-xl font-semibold">{copy.processVideo.title}</h2>
						<CardDescription id="process-video-help">
							{copy.processVideo.description}
						</CardDescription>
					</CardHeader>
					<CardContent>
						<form
							action={processVideoAction}
							className="grid gap-4"
							data-auto-disable-required="true"
						>
							<input
								type="hidden"
								name="session_token"
								value={sessionToken}
								suppressHydrationWarning
							/>
							<FormSelectField
								id="process-platform"
								label={copy.processVideo.platformLabel}
								name="platform"
								defaultValue="youtube"
								options={PROCESS_PLATFORM_OPTIONS}
								required
							/>
							<FormInputField
								id="process-url"
								label={copy.processVideo.urlLabel}
								name="url"
								type="url"
								required
								placeholder="https://www.youtube.com/watch?v=..."
								data-field-kind="url"
							/>
							<FormSelectField
								id="process-mode"
								label={copy.processVideo.modeLabel}
								name="mode"
								defaultValue="full"
								options={PROCESS_MODE_OPTIONS}
								required
							/>
							<FormCheckboxField
								id="force-run"
								name="force"
								label={copy.processVideo.forceLabel}
							/>
							<div className="flex flex-wrap items-center gap-3">
								<SubmitButton
									pendingLabel={copy.processVideo.submitPending}
									statusText={copy.processVideo.submitStatus}
								>
									{copy.processVideo.submit}
								</SubmitButton>
								<Button asChild variant="outline" size="sm">
									<Link href="/jobs">{copy.processVideo.jobDetailLink}</Link>
								</Button>
							</div>
						</form>
					</CardContent>
				</Card>
			</section>

			<section>
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<h2 className="text-xl font-semibold">{copy.ingestRuns.title}</h2>
						<CardDescription>{copy.ingestRuns.description}</CardDescription>
					</CardHeader>
					<CardContent className="space-y-3">
						<Button asChild variant="link" size="sm" className="h-auto px-0">
							<Link href="/ingest-runs">{copy.ingestRuns.viewAll}</Link>
						</Button>
						{ingestRunsUnavailable ? (
							<output
								className="text-sm text-muted-foreground"
								aria-live="polite"
								aria-atomic="true"
							>
								{copy.ingestRuns.unavailable}
							</output>
						) : null}
						{!ingestRunsUnavailable && ingestRuns.length === 0 ? (
							<output
								className="text-sm text-muted-foreground"
								aria-live="polite"
								aria-atomic="true"
							>
								{copy.ingestRuns.empty}
							</output>
						) : null}
						{!ingestRunsUnavailable && ingestRuns.length > 0 ? (
							<div className="overflow-x-auto rounded-lg border border-border/70">
								<table className="min-w-[720px] w-full text-sm">
									<caption className="sr-only">
										{copy.ingestRuns.caption}
									</caption>
									<thead className="bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
										<tr>
											<th scope="col" className="px-4 py-3 font-medium">
												Run ID
											</th>
											<th scope="col" className="px-4 py-3 font-medium">
												{copy.ingestRuns.platform}
											</th>
											<th scope="col" className="px-4 py-3 font-medium">
												{copy.ingestRuns.status}
											</th>
											<th scope="col" className="px-4 py-3 font-medium">
												{copy.ingestRuns.newJobs}
											</th>
											<th scope="col" className="px-4 py-3 font-medium">
												{copy.ingestRuns.candidates}
											</th>
										</tr>
									</thead>
									<tbody>
										{ingestRuns.map((run) => (
											<tr key={run.id} className="border-t border-border/60">
												<td className="px-4 py-3 align-top font-mono text-xs">
													<Link
														href={`/ingest-runs?run_id=${encodeURIComponent(run.id)}`}
														className="text-primary underline-offset-4 hover:underline"
													>
														{run.id}
													</Link>
												</td>
												<td className="px-4 py-3 align-top">
													{run.platform
														? toPlatformLabel(run.platform)
														: copy.ingestRuns.allPlatforms}
												</td>
												<td className="px-4 py-3 align-top">
													<DashboardStatusBadge status={run.status} />
												</td>
												<td className="px-4 py-3 align-top">
													{run.jobs_created}
												</td>
												<td className="px-4 py-3 align-top">
													{run.candidates_count}
												</td>
											</tr>
										))}
									</tbody>
								</table>
							</div>
						) : null}
					</CardContent>
				</Card>
			</section>

			<section>
				<Card className="folo-surface border-border/70">
					<CardHeader className="flex flex-row items-start justify-between gap-4">
						<div className="space-y-2">
							<h2 className="text-xl font-semibold">
								{copy.recentVideos.title}
							</h2>
							<CardDescription>{copy.recentVideos.description}</CardDescription>
						</div>
						<Button asChild variant="link" size="sm" className="h-auto px-0">
							<Link href="/jobs">{copy.recentVideos.viewAll}</Link>
						</Button>
					</CardHeader>
					<CardContent className="space-y-3">
						{videos.length === 0 && !loadErrorCode ? (
							<output
								className="text-sm text-muted-foreground"
								aria-live="polite"
								aria-atomic="true"
							>
								{copy.recentVideos.empty}
							</output>
						) : null}
						{videos.length === 0 && loadErrorCode ? (
							<output
								className="text-sm text-muted-foreground"
								aria-live="polite"
								aria-atomic="true"
							>
								{copy.recentVideos.unavailable}
							</output>
						) : null}
						{videos.length > 0 ? (
							<div className="overflow-x-auto rounded-lg border border-border/70">
								<table className="min-w-[680px] w-full text-sm">
									<caption className="sr-only">
										{copy.recentVideos.caption}
									</caption>
									<thead className="bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
										<tr>
											<th scope="col" className="px-4 py-3 font-medium">
												{copy.recentVideos.titleColumn}
											</th>
											<th scope="col" className="px-4 py-3 font-medium">
												{copy.recentVideos.platformColumn}
											</th>
											<th scope="col" className="px-4 py-3 font-medium">
												{copy.recentVideos.statusColumn}
											</th>
											<th scope="col" className="px-4 py-3 font-medium">
												{copy.recentVideos.lastJobColumn}
											</th>
										</tr>
									</thead>
									<tbody>
										{videos.slice(0, 10).map((video) => (
											<tr key={video.id} className="border-t border-border/60">
												<td className="px-4 py-3 align-top">
													{video.title ?? video.video_uid}
												</td>
												<td className="px-4 py-3 align-top">
													{toPlatformLabel(video.platform)}
												</td>
												<td className="px-4 py-3 align-top">
													<DashboardStatusBadge status={video.status} />
												</td>
												<td className="px-4 py-3 align-top">
													{video.last_job_id ? (
														<Button
															asChild
															variant="link"
															size="sm"
															className="h-auto px-0"
														>
															<Link
																href={`/jobs?job_id=${encodeURIComponent(video.last_job_id)}`}
															>
																{video.last_job_id}
															</Link>
														</Button>
													) : (
														"-"
													)}
												</td>
											</tr>
										))}
									</tbody>
								</table>
							</div>
						) : null}
					</CardContent>
				</Card>
			</section>
		</div>
	);
}
