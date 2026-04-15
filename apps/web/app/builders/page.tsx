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

const RESOURCE_LINKS = {
	builders:
		"https://github.com/xiaojiou176-open/sourceharbor/blob/main/docs/builders.md",
	distribution:
		"https://github.com/xiaojiou176-open/sourceharbor/blob/main/docs/public-distribution.md",
	starterPacks:
		"https://github.com/xiaojiou176-open/sourceharbor/blob/main/starter-packs/README.md",
	cli: "https://github.com/xiaojiou176-open/sourceharbor/blob/main/packages/sourceharbor-cli/README.md",
	sdk: "https://github.com/xiaojiou176-open/sourceharbor/blob/main/packages/sourceharbor-sdk/README.md",
	codexBundle:
		"https://github.com/xiaojiou176-open/sourceharbor/blob/main/starter-packs/codex/sourceharbor-codex-plugin/README.md",
	claudeBundle:
		"https://github.com/xiaojiou176-open/sourceharbor/blob/main/starter-packs/claude-code/sourceharbor-claude-plugin/README.md",
	openclawBundle:
		"https://github.com/xiaojiou176-open/sourceharbor/blob/main/starter-packs/openclaw/README.md",
	mcpRegistry:
		"https://github.com/xiaojiou176-open/sourceharbor/blob/main/starter-packs/mcp-registry/README.md",
	codexCompat:
		"https://github.com/xiaojiou176-open/sourceharbor/blob/main/docs/compat/codex.md",
	claudeCompat:
		"https://github.com/xiaojiou176-open/sourceharbor/blob/main/docs/compat/claude-code.md",
	openclawCompat:
		"https://github.com/xiaojiou176-open/sourceharbor/blob/main/docs/compat/openclaw.md",
	publicSkills:
		"https://github.com/xiaojiou176-open/sourceharbor/blob/main/docs/public-skills.md",
	projectStatus:
		"https://github.com/xiaojiou176-open/sourceharbor/blob/main/docs/project-status.md",
	mediaKit:
		"https://github.com/xiaojiou176-open/sourceharbor/blob/main/docs/media-kit.md",
} as const;

const OFFICIAL_SURFACE_ROWS = [
	{
		name: "Codex",
		status: "Bundle-ready",
		tone: "secondary" as const,
		snapshot: "Official directory proof still missing.",
		summary:
			"SourceHarbor already ships a Codex-compatible plugin bundle, but there is still no official self-serve public directory path to claim as live listing proof.",
		href: RESOURCE_LINKS.codexCompat,
		cta: "Open Codex boundary",
	},
	{
		name: "Claude Code",
		status: "Submission-ready",
		tone: "secondary" as const,
		snapshot: "Marketplace review is still the real gate.",
		summary:
			"The plugin bundle and starter pack are ready for the official path, but live listing proof still depends on Anthropic review and marketplace policy.",
		href: RESOURCE_LINKS.claudeCompat,
		cta: "Open Claude boundary",
	},
	{
		name: "OpenClaw / ClawHub",
		status: "Template-ready",
		tone: "outline" as const,
		snapshot: "Live registry receipt has not been captured yet.",
		summary:
			"SourceHarbor now has a first-cut OpenClaw pack plus publish-ready ClawHub metadata, but not a live public registry receipt yet.",
		href: RESOURCE_LINKS.openclawCompat,
		cta: "Open OpenClaw boundary",
	},
	{
		name: "Official MCP Registry",
		status: "Listed, refresh blocked",
		tone: "secondary" as const,
		snapshot: "Live entry exists at 0.1.14; refresh to 0.1.19 is credential-blocked.",
		summary:
			"The official registry entry and PyPI package already exist publicly at 0.1.14. The repo-controlled package line is 0.1.19, so the remaining step is a credentialed refresh, not first-time publication.",
		href: RESOURCE_LINKS.mcpRegistry,
		cta: "Open MCP registry pack",
	},
] as const;

const HUMAN_ONLY_STEPS = [
	"Submit official marketplace or registry forms when a platform still needs human login, CAPTCHA, or irreversible account confirmation.",
	"Upload the tracked GitHub social preview asset in repo settings after the PNG is ready to use.",
	"Treat payment, legal, identity, or organization-scoped profile settings as human-only finish-line steps.",
] as const;

const builderCopy = getLocaleMessages().builderSurfaces;

export const metadata: Metadata = buildProductMetadata({
	title: "Builders",
	description:
		"Choose one SourceHarbor builder first hop for MCP, Codex, Claude Code, OpenClaw, CLI, SDK, and proof-first adoption.",
	route: "builders",
	keywords: [
		"SourceHarbor builders",
		"Codex workflow",
		"Claude Code workflow",
		"OpenClaw starter pack",
		"MCP registry",
		"plugin bundle",
	],
});

export default function BuildersPage() {
	const cards = builderCopy.cards;
	const atlasRows = [cards.reuse, cards.proof, cards.compounders] as const;

	return (
		<div className="folo-page-shell folo-unified-shell">
			<div className="folo-page-header">
				<p className="folo-page-kicker">SourceHarbor Builder Entry</p>
				<h1 className="folo-page-title" data-route-heading tabIndex={-1}>
					{builderCopy.title}
				</h1>
				<p className="folo-page-subtitle">{builderCopy.subtitle}</p>
				<div className="mt-4 flex flex-wrap gap-3 text-sm text-muted-foreground">
					<Link
						href="/reader"
						className="underline underline-offset-4 hover:text-foreground"
					>
						Back to Reader
					</Link>
					<Link
						href="/feed"
						className="underline underline-offset-4 hover:text-foreground"
					>
						Back to Feed
					</Link>
				</div>
			</div>

			<section className="grid gap-4 xl:grid-cols-[1.1fr_0.92fr]">
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<h2 className="text-2xl font-semibold leading-none">
							Pick one builder lane only after reading
						</h2>
						<CardDescription>
							Reader and Feed stay first. Open this page only when you already
							know you need an integration lane.
						</CardDescription>
					</CardHeader>
					<CardContent className="space-y-6">
						<div className="grid gap-3 lg:grid-cols-2">
							<Button asChild variant="hero" className="justify-start">
								<Link href="/mcp">{builderCopy.mcpCta}</Link>
							</Button>
							<div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
								<Link
									href="/use-cases/codex"
									className="underline underline-offset-4 hover:text-foreground"
								>
									{builderCopy.codexCta}
								</Link>
								<Link
									href="/use-cases/claude-code"
									className="underline underline-offset-4 hover:text-foreground"
								>
									{builderCopy.claudeCodeCta}
								</Link>
							</div>
						</div>
						<p className="text-sm leading-7 text-muted-foreground">
							Start with one tool lane only. Open proof, packages, and starter packs after you already know which door you need.
						</p>
					</CardContent>
				</Card>

				<Card className="folo-surface border-border/70">
					<CardHeader>
						<h2 className="text-2xl font-semibold leading-none">
							Keep the rest as a reference map
						</h2>
						<CardDescription>
							Use this only after you already picked the lane you need. It is
							a map, not the first doorway.
						</CardDescription>
					</CardHeader>
					<CardContent className="space-y-4">
						{atlasRows.map((section, index) => (
							<div
								key={section.title}
								className={
									index === 0
										? "space-y-3"
										: "space-y-3 border-t border-border/50 pt-4"
								}
							>
								<div className="space-y-1">
									<p className="text-base font-semibold text-foreground">
										{section.title}
									</p>
									<p className="text-sm leading-6 text-muted-foreground">
										{section.description}
									</p>
								</div>
								<div className="flex flex-wrap gap-2">
									{section.bullets.map((item) => (
										<Badge
											key={item}
											variant="outline"
											className="bg-background/70"
										>
											{item}
										</Badge>
									))}
								</div>
							</div>
						))}
					</CardContent>
				</Card>
			</section>

			<section className="grid gap-4 xl:grid-cols-[0.94fr_1.06fr]">
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<CardTitle>Read this only after you pick a lane</CardTitle>
						<CardDescription>{builderCopy.resourceDescription}</CardDescription>
					</CardHeader>
					<CardContent className="grid gap-6 text-sm text-muted-foreground md:grid-cols-2">
						<div className="space-y-3">
							<p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">
								Docs and starter packs
							</p>
							<ul className="space-y-3">
								<li>
									<a
										className="font-medium text-foreground underline decoration-border underline-offset-4 hover:text-primary"
										href={RESOURCE_LINKS.builders}
										target="_blank"
										rel="noreferrer"
									>
										{builderCopy.buildersGuideCta}
									</a>
								</li>
								<li>
									<a
										className="font-medium text-foreground underline decoration-border underline-offset-4 hover:text-primary"
										href={RESOURCE_LINKS.starterPacks}
										target="_blank"
										rel="noreferrer"
									>
										{builderCopy.starterPacksCta}
									</a>
								</li>
								<li>
									<a
										className="font-medium text-foreground underline decoration-border underline-offset-4 hover:text-primary"
										href={RESOURCE_LINKS.distribution}
										target="_blank"
										rel="noreferrer"
									>
										Open distribution ledger
									</a>
								</li>
							</ul>
						</div>
						<div className="space-y-3">
							<p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">
								Packages and public proof
							</p>
							<ul className="space-y-3">
								<li>
									<a
										className="font-medium text-foreground underline decoration-border underline-offset-4 hover:text-primary"
										href={RESOURCE_LINKS.cli}
										target="_blank"
										rel="noreferrer"
									>
										{builderCopy.cliPackageCta}
									</a>
								</li>
								<li>
									<a
										className="font-medium text-foreground underline decoration-border underline-offset-4 hover:text-primary"
										href={RESOURCE_LINKS.sdk}
										target="_blank"
										rel="noreferrer"
									>
										{builderCopy.sdkPackageCta}
									</a>
								</li>
								<li>
									<a
										className="font-medium text-foreground underline decoration-border underline-offset-4 hover:text-primary"
										href={RESOURCE_LINKS.projectStatus}
										target="_blank"
										rel="noreferrer"
									>
										Open current status board
									</a>
								</li>
								<li>
									<a
										className="font-medium text-foreground underline decoration-border underline-offset-4 hover:text-primary"
										href={RESOURCE_LINKS.publicSkills}
										target="_blank"
										rel="noreferrer"
									>
										Open public skills guide
									</a>
								</li>
								<li>
									<a
										className="font-medium text-foreground underline decoration-border underline-offset-4 hover:text-primary"
										href={RESOURCE_LINKS.mediaKit}
										target="_blank"
										rel="noreferrer"
									>
										Open media kit
									</a>
								</li>
							</ul>
						</div>
					</CardContent>
				</Card>

				<Card className="folo-surface border-border/70">
					<CardHeader>
						<CardTitle>What is already public</CardTitle>
						<CardDescription>
							Use this as a quick status board, not as the main reading
							experience.
						</CardDescription>
					</CardHeader>
					<CardContent className="space-y-4 text-sm text-muted-foreground">
						{OFFICIAL_SURFACE_ROWS.map((item, index) => (
							<div
								key={item.name}
								className={
									index === 0
										? "space-y-3"
										: "space-y-3 border-t border-border/50 pt-4"
								}
							>
								<div className="flex flex-wrap items-center justify-between gap-3">
									<p className="font-medium text-foreground">{item.name}</p>
									<Badge variant={item.tone}>{item.status}</Badge>
								</div>
								<p>{item.snapshot}</p>
								<a
									href={item.href}
									target="_blank"
									rel="noreferrer"
									className="inline-flex items-center text-sm text-muted-foreground underline underline-offset-4 hover:text-foreground"
								>
									{item.cta}
								</a>
							</div>
						))}
					</CardContent>
				</Card>
			</section>

			<Card className="folo-surface border-border/70">
				<CardHeader>
					<CardTitle>Packages and templates</CardTitle>
					<CardDescription>
						Open one concrete package or template only when you already know
						which builder path you need.
					</CardDescription>
				</CardHeader>
				<CardContent className="grid gap-4 text-sm text-muted-foreground md:grid-cols-2 xl:grid-cols-4">
					<div className="space-y-3 rounded-lg border border-border/60 bg-background/55 p-4">
						<p className="font-medium text-foreground">Codex bundle</p>
						<p>
							Open the plugin-grade package when you need the real install
							surface.
						</p>
						<a
							href={RESOURCE_LINKS.codexBundle}
							target="_blank"
							rel="noreferrer"
							className="inline-flex items-center text-sm text-muted-foreground underline underline-offset-4 hover:text-foreground"
						>
							Inspect Codex bundle
						</a>
					</div>
					<div className="space-y-3 rounded-lg border border-border/60 bg-background/55 p-4">
						<p className="font-medium text-foreground">Claude bundle</p>
						<p>
							Open the starter pack that is ready for official path submission.
						</p>
						<a
							href={RESOURCE_LINKS.claudeBundle}
							target="_blank"
							rel="noreferrer"
							className="inline-flex items-center text-sm text-muted-foreground underline underline-offset-4 hover:text-foreground"
						>
							Inspect Claude bundle
						</a>
					</div>
					<div className="space-y-3 rounded-lg border border-border/60 bg-background/55 p-4">
						<p className="font-medium text-foreground">OpenClaw pack</p>
						<p>
							Inspect the publish-ready pack and template layer for OpenClaw.
						</p>
						<a
							href={RESOURCE_LINKS.openclawBundle}
							target="_blank"
							rel="noreferrer"
							className="inline-flex items-center text-sm text-muted-foreground underline underline-offset-4 hover:text-foreground"
						>
							Inspect OpenClaw pack
						</a>
					</div>
					<div className="space-y-3 rounded-lg border border-border/60 bg-background/55 p-4">
						<p className="font-medium text-foreground">Registry template</p>
						<p>
							Use the official-registry-shaped template when you need metadata
							receipts.
						</p>
						<a
							href={RESOURCE_LINKS.mcpRegistry}
							target="_blank"
							rel="noreferrer"
							className="inline-flex items-center text-sm text-muted-foreground underline underline-offset-4 hover:text-foreground"
						>
							Inspect MCP registry template
						</a>
					</div>
				</CardContent>
			</Card>

			<section className="grid gap-4 lg:grid-cols-[1.1fr_1fr]">
				<details className="group rounded-xl border border-border/70 bg-card text-card-foreground folo-surface">
					<summary className="flex cursor-pointer list-none items-start justify-between gap-4 px-6 py-6 marker:content-none [&::-webkit-details-marker]:hidden">
						<div className="space-y-2">
							<p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
								Later proof lane
							</p>
							<h3 className="text-xl font-semibold">
								What still needs external proof
							</h3>
							<p className="max-w-[52ch] text-sm leading-6 text-muted-foreground">
								These are the pieces that still depend on a real marketplace,
								registry, or review receipt.
							</p>
						</div>
						<span className="rounded-full border border-border/60 bg-background/70 px-3 py-1 text-xs font-medium text-muted-foreground transition group-open:text-foreground">
							Expand
						</span>
					</summary>
					<div className="border-t border-border/50 px-6 pb-6 pt-4 text-sm text-muted-foreground">
						<p>
							Start from the package or template that already exists, then keep
							one ledger per platform:
						</p>
						<ul className="mt-3 list-disc space-y-2 pl-5">
							<li>submission artifact</li>
							<li>listing or review URL</li>
							<li>pending-review or receipt proof</li>
							<li>exact blocker when the platform still needs a human step</li>
						</ul>
						<div className="mt-4 flex flex-wrap gap-3">
							<Button asChild variant="outline" size="sm">
								<a
									href={RESOURCE_LINKS.projectStatus}
									target="_blank"
									rel="noreferrer"
								>
									Open current status board
								</a>
							</Button>
							<Button asChild variant="outline" size="sm">
								<a
									href={RESOURCE_LINKS.publicSkills}
									target="_blank"
									rel="noreferrer"
								>
									Open public skills guide
								</a>
							</Button>
						</div>
					</div>
				</details>

				<details className="group rounded-xl border border-border/70 bg-card text-card-foreground folo-surface">
					<summary className="flex cursor-pointer list-none items-start justify-between gap-4 px-6 py-6 marker:content-none [&::-webkit-details-marker]:hidden">
						<div className="space-y-2">
							<p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
								Manual-only boundary
							</p>
							<h3 className="text-xl font-semibold">Human-only finish line</h3>
							<p className="max-w-[48ch] text-sm leading-6 text-muted-foreground">
								Keep the automation boundary honest. Repo-side engineering and
								package prep can keep moving; these last-mile steps should only
								move when a human must really click or confirm.
							</p>
						</div>
						<span className="rounded-full border border-border/60 bg-background/70 px-3 py-1 text-xs font-medium text-muted-foreground transition group-open:text-foreground">
							Expand
						</span>
					</summary>
					<div className="border-t border-border/50 px-6 pb-6 pt-4 text-sm text-muted-foreground">
						<div className="space-y-2">
							{HUMAN_ONLY_STEPS.map((item) => (
								<p key={item}>{item}</p>
							))}
						</div>
					</div>
				</details>
			</section>
		</div>
	);
}
