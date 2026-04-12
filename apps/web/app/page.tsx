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
import { getLocaleMessages } from "@/lib/i18n/messages";
import { buildProductMetadata } from "@/lib/seo";

const dashboardCopy = getLocaleMessages().dashboard;

export const metadata: Metadata = buildProductMetadata({
	title: dashboardCopy.metadataTitle,
	description: dashboardCopy.metadataDescription,
	route: "dashboard",
});

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
		status: "Bundle ships now, official listing still unverified",
		detail:
			"Source-installable bundle exists today, but any official marketplace listing still needs submit and read-back proof.",
	},
	{
		name: "OpenClaw / ClawHub",
		status: "OpenClaw pack ships now, ClawHub still needs owner publish",
		detail:
			"Repo pack and publish-shaped template exist, but a live ClawHub receipt still depends on owner login and publish.",
	},
	{
		name: "Official MCP Registry",
		status: "Live listed at 0.1.14, repo packet is ahead",
		detail:
			"The registry entry is already live, while the repo-tracked package and directory packet have moved ahead of the public version.",
	},
] as const;

export default function DashboardPage() {
	const messages = getLocaleMessages();
	const copy = messages.dashboard;
	const builderCopy = messages.builderSurfaces;
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
	const builderCards = [
		builderCopy.cards.reuse,
		builderCopy.cards.proof,
		builderCopy.cards.compounders,
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

	return (
		<div className="folo-page-shell folo-unified-shell">
			<div className="folo-page-header">
				<p className="folo-page-kicker">{copy.kicker}</p>
				<h1 className="folo-page-title" data-route-heading tabIndex={-1}>
					{copy.heroTitle}
				</h1>
				<p className="folo-page-subtitle">{copy.heroSubtitle}</p>
			</div>

			<section
				className="grid gap-4 xl:grid-cols-3"
				aria-label="Why this front door works"
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
				aria-label="Choose your first route"
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
							<Link href="/reader">{copy.firstHop.evaluatePrimaryCta}</Link>
						</Button>
						<Button asChild variant="outline">
							<Link href="/reader/demo">
								{copy.firstHop.evaluateSecondaryCta}
							</Link>
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
							<Link href="/subscriptions">
								{copy.firstHop.operatePrimaryCta}
							</Link>
						</Button>
						<Button asChild variant="outline">
							<Link href="/feed">{copy.firstHop.operateSecondaryCta}</Link>
						</Button>
						<Button asChild variant="outline">
							<Link href="/trends">{copy.firstHop.operateTertiaryCta}</Link>
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
							<Link href="/ops">{copy.firstHop.buildTertiaryCta}</Link>
						</Button>
					</CardContent>
				</Card>
			</section>

			<section
				className="grid gap-4 xl:grid-cols-5"
				aria-label="SourceHarbor front doors"
			>
				<h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-muted-foreground xl:col-span-5">
					{copy.sectionHeadings.primaryFrontDoors}
				</h2>
				<Card className="folo-surface border-border/70 xl:col-span-1">
					<CardHeader>
						<CardTitle>Reader</CardTitle>
						<CardDescription>
							Open the published-doc frontstage where merge docs, singleton
							polish docs, navigation brief, and yellow-warning honesty now live
							on one surface.
						</CardDescription>
					</CardHeader>
					<CardContent className="space-y-3 pt-0">
						<div className="flex flex-wrap items-center gap-3">
							<Button asChild>
								<Link href="/reader">Open Reader</Link>
							</Button>
							<Button asChild variant="outline">
								<Link href="/briefings">Open Briefings</Link>
							</Button>
						</div>
						<p className="text-sm text-muted-foreground">
							Use this when you want the actual reading product, not the
							operator controls or raw job trace.
						</p>
					</CardContent>
				</Card>
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
		</div>
	);
}
