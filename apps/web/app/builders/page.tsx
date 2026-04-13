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
		status: "Metadata-ready",
		tone: "outline" as const,
		snapshot: "Namespace proof and install artifact are still pending.",
		summary:
			"The official-registry-shaped server template exists today, but real publication still needs a public install artifact and verified namespace ownership.",
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
			</div>

			<section className="grid gap-4 xl:grid-cols-[1.1fr_0.92fr]">
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<div className="flex flex-wrap gap-2">
							{builderCopy.highlightPills.map((pill) => (
								<Badge
									key={pill}
									variant="outline"
									className="bg-background/70"
								>
									{pill}
								</Badge>
							))}
						</div>
						<h2 className="text-2xl font-semibold leading-none">
							Start from one honest door
						</h2>
						<CardDescription>
							Pick the narrowest entry that matches what you actually need
							first. You do not have to learn every surface before you take the
							first step.
						</CardDescription>
					</CardHeader>
					<CardContent className="space-y-6">
						<div className="grid gap-3 lg:grid-cols-2">
							<Button asChild variant="hero" className="justify-start">
								<Link href="/mcp">{builderCopy.mcpCta}</Link>
							</Button>
							<Button asChild variant="surface" className="justify-start">
								<Link href="/use-cases/codex">{builderCopy.codexCta}</Link>
							</Button>
							<Button asChild variant="surface" className="justify-start">
								<Link href="/use-cases/claude-code">
									{builderCopy.claudeCodeCta}
								</Link>
							</Button>
							<Button asChild variant="ghost" className="justify-start">
								<Link href="/proof">{builderCopy.proofCta}</Link>
							</Button>
						</div>
						<div className="grid gap-3 rounded-2xl border border-border/60 bg-background/55 p-4 text-sm text-muted-foreground">
							<p className="font-semibold text-foreground">
								Choose the first builder lane, not the whole stack
							</p>
							<ul className="space-y-2">
								<li className="flex gap-3">
									<span
										className="mt-2 size-1.5 shrink-0 rounded-full bg-primary/80"
										aria-hidden
									/>
									<span>
										Open MCP when you want the fastest agent-facing entry that
										reuses the same retrieval, jobs, and proof surfaces.
									</span>
								</li>
								<li className="flex gap-3">
									<span
										className="mt-2 size-1.5 shrink-0 rounded-full bg-primary/80"
										aria-hidden
									/>
									<span>
										Open a workflow page when you want a guided Codex or Claude
										Code operator path instead of raw protocol docs.
									</span>
								</li>
								<li className="flex gap-3">
									<span
										className="mt-2 size-1.5 shrink-0 rounded-full bg-primary/80"
										aria-hidden
									/>
									<span>
										Inspect proof when you need the honest answer to what is
										live, preview-only, or still blocked on external review.
									</span>
								</li>
							</ul>
						</div>
					</CardContent>
				</Card>

				<Card className="folo-surface border-border/70">
					<CardHeader>
						<h2 className="text-2xl font-semibold leading-none">
							Builder atlas
						</h2>
						<CardDescription>
							SourceHarbor is easiest to understand when the builder story is
							split into one map: control plane, proof line, and compounder
							return loop.
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
						<CardTitle>{builderCopy.resourceTitle}</CardTitle>
						<CardDescription>{builderCopy.resourceDescription}</CardDescription>
					</CardHeader>
					<CardContent className="grid gap-4 text-sm text-muted-foreground md:grid-cols-2">
						<div className="space-y-3">
							<p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">
								Docs and starter packs
							</p>
							<div className="flex flex-wrap gap-3">
								<Button asChild variant="outline" size="sm">
									<a
										href={RESOURCE_LINKS.builders}
										target="_blank"
										rel="noreferrer"
									>
										{builderCopy.buildersGuideCta}
									</a>
								</Button>
								<Button asChild variant="outline" size="sm">
									<a
										href={RESOURCE_LINKS.starterPacks}
										target="_blank"
										rel="noreferrer"
									>
										{builderCopy.starterPacksCta}
									</a>
								</Button>
								<Button asChild variant="outline" size="sm">
									<a
										href={RESOURCE_LINKS.distribution}
										target="_blank"
										rel="noreferrer"
									>
										Open distribution ledger
									</a>
								</Button>
							</div>
						</div>
						<div className="space-y-3">
							<p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">
								Packages and public proof
							</p>
							<div className="flex flex-wrap gap-3">
								<Button asChild variant="outline" size="sm">
									<a href={RESOURCE_LINKS.cli} target="_blank" rel="noreferrer">
										{builderCopy.cliPackageCta}
									</a>
								</Button>
								<Button asChild variant="outline" size="sm">
									<a href={RESOURCE_LINKS.sdk} target="_blank" rel="noreferrer">
										{builderCopy.sdkPackageCta}
									</a>
								</Button>
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
								<Button asChild variant="outline" size="sm">
									<a
										href={RESOURCE_LINKS.mediaKit}
										target="_blank"
										rel="noreferrer"
									>
										Open media kit
									</a>
								</Button>
							</div>
						</div>
					</CardContent>
				</Card>

				<Card className="folo-surface border-border/70">
					<CardHeader>
						<CardTitle>Current official-surface status</CardTitle>
						<CardDescription>
							These are the strongest public distribution artifacts today. They
							are not the same thing as a live official listing until the target
							platform returns a receipt, review URL, or published entry.
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
								<div className="flex flex-wrap gap-3">
									<Button asChild variant="outline" size="sm">
										<a href={item.href} target="_blank" rel="noreferrer">
											{item.cta}
										</a>
									</Button>
								</div>
							</div>
						))}
					</CardContent>
				</Card>
			</section>

			<Card className="folo-surface border-border/70">
				<CardHeader>
					<CardTitle>Bundle receipts and registry-ready templates</CardTitle>
					<CardDescription>
						These are the concrete distribution artifacts behind today&apos;s
						builder story when you need the actual bundle or template, not just
						the route map.
					</CardDescription>
				</CardHeader>
				<CardContent className="grid gap-4 text-sm text-muted-foreground md:grid-cols-2 xl:grid-cols-4">
					<div className="space-y-3 rounded-lg border border-border/60 bg-background/55 p-4">
						<p className="font-medium text-foreground">Codex bundle</p>
						<p>
							Open the plugin-grade package when you need the real install
							surface.
						</p>
						<Button asChild variant="outline" size="sm">
							<a
								href={RESOURCE_LINKS.codexBundle}
								target="_blank"
								rel="noreferrer"
							>
								Inspect Codex bundle
							</a>
						</Button>
					</div>
					<div className="space-y-3 rounded-lg border border-border/60 bg-background/55 p-4">
						<p className="font-medium text-foreground">Claude bundle</p>
						<p>
							Open the starter pack that is ready for official path submission.
						</p>
						<Button asChild variant="outline" size="sm">
							<a
								href={RESOURCE_LINKS.claudeBundle}
								target="_blank"
								rel="noreferrer"
							>
								Inspect Claude bundle
							</a>
						</Button>
					</div>
					<div className="space-y-3 rounded-lg border border-border/60 bg-background/55 p-4">
						<p className="font-medium text-foreground">OpenClaw pack</p>
						<p>
							Inspect the publish-ready pack and template layer for OpenClaw.
						</p>
						<Button asChild variant="outline" size="sm">
							<a
								href={RESOURCE_LINKS.openclawBundle}
								target="_blank"
								rel="noreferrer"
							>
								Inspect OpenClaw pack
							</a>
						</Button>
					</div>
					<div className="space-y-3 rounded-lg border border-border/60 bg-background/55 p-4">
						<p className="font-medium text-foreground">Registry template</p>
						<p>
							Use the official-registry-shaped template when you need metadata
							receipts.
						</p>
						<Button asChild variant="outline" size="sm">
							<a
								href={RESOURCE_LINKS.mcpRegistry}
								target="_blank"
								rel="noreferrer"
							>
								Inspect MCP registry template
							</a>
						</Button>
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
								What still needs live submission proof
							</h3>
							<p className="max-w-[52ch] text-sm leading-6 text-muted-foreground">
								The repo now has real bundles, templates, and starter packs. The
								next bar is no longer “write another README”, but “show a real
								submission, listing, pending-review URL, or exact external
								blocker.”
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
