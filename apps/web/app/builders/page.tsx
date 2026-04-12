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
		summary:
			"SourceHarbor already ships a Codex-compatible plugin bundle, but there is still no official self-serve public directory path to claim as live listing proof.",
		href: RESOURCE_LINKS.codexCompat,
		cta: "Open Codex boundary",
	},
	{
		name: "Claude Code",
		status: "Submission-ready",
		tone: "secondary" as const,
		summary:
			"The plugin bundle and starter pack are ready for the official path, but live listing proof still depends on Anthropic review and marketplace policy.",
		href: RESOURCE_LINKS.claudeCompat,
		cta: "Open Claude boundary",
	},
	{
		name: "OpenClaw / ClawHub",
		status: "Template-ready",
		tone: "outline" as const,
		summary:
			"SourceHarbor now has a first-cut OpenClaw pack plus publish-ready ClawHub metadata, but not a live public registry receipt yet.",
		href: RESOURCE_LINKS.openclawCompat,
		cta: "Open OpenClaw boundary",
	},
	{
		name: "Official MCP Registry",
		status: "Metadata-ready",
		tone: "outline" as const,
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

	return (
		<div className="folo-page-shell folo-unified-shell">
			<div className="folo-page-header">
				<p className="folo-page-kicker">SourceHarbor Builder Entry</p>
				<h1 className="folo-page-title" data-route-heading tabIndex={-1}>
					{builderCopy.title}
				</h1>
				<p className="folo-page-subtitle">{builderCopy.subtitle}</p>
			</div>

			<Card className="folo-surface border-border/70">
				<CardHeader>
					<CardTitle>Start from one honest door</CardTitle>
					<CardDescription>
						Pick the narrowest entry that matches what you actually need first.
						You do not have to learn every surface before you take the first
						step.
					</CardDescription>
				</CardHeader>
				<CardContent className="flex flex-wrap gap-3">
					<Button asChild>
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
					<Button asChild variant="ghost">
						<Link href="/proof">{builderCopy.proofCta}</Link>
					</Button>
				</CardContent>
			</Card>

			<section className="grid gap-4 lg:grid-cols-3">
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<CardTitle>{cards.reuse.title}</CardTitle>
						<CardDescription>{cards.reuse.description}</CardDescription>
					</CardHeader>
					<CardContent className="space-y-2 text-sm text-muted-foreground">
						{cards.reuse.bullets.map((item) => (
							<p key={item}>{item}</p>
						))}
					</CardContent>
				</Card>
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<CardTitle>{cards.proof.title}</CardTitle>
						<CardDescription>{cards.proof.description}</CardDescription>
					</CardHeader>
					<CardContent className="space-y-2 text-sm text-muted-foreground">
						{cards.proof.bullets.map((item) => (
							<p key={item}>{item}</p>
						))}
					</CardContent>
				</Card>
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<CardTitle>{cards.compounders.title}</CardTitle>
						<CardDescription>{cards.compounders.description}</CardDescription>
					</CardHeader>
					<CardContent className="space-y-2 text-sm text-muted-foreground">
						{cards.compounders.bullets.map((item) => (
							<p key={item}>{item}</p>
						))}
					</CardContent>
				</Card>
			</section>

			<Card className="folo-surface border-border/70">
				<CardHeader>
					<CardTitle>{builderCopy.resourceTitle}</CardTitle>
					<CardDescription>{builderCopy.resourceDescription}</CardDescription>
				</CardHeader>
				<CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
					<Button asChild variant="outline" size="sm">
						<a href={RESOURCE_LINKS.builders} target="_blank" rel="noreferrer">
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
						<a href={RESOURCE_LINKS.mediaKit} target="_blank" rel="noreferrer">
							Open media kit
						</a>
					</Button>
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
				<CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-4 text-sm text-muted-foreground">
					<div className="rounded-lg border border-border/60 bg-muted/20 p-4">
						<p className="font-medium text-foreground">Codex</p>
						<p className="mt-2">
							Plugin-grade bundle is real today. Official directory self-serve
							listing is still not open, so the next honest step is
							submit/read-back on the strongest public surface that exists.
						</p>
					</div>
					<div className="rounded-lg border border-border/60 bg-muted/20 p-4">
						<p className="font-medium text-foreground">Claude Code</p>
						<p className="mt-2">
							Submission-ready bundle exists now. Live listing still depends on
							Anthropic review and the marketplace flow.
						</p>
					</div>
					<div className="rounded-lg border border-border/60 bg-muted/20 p-4">
						<p className="font-medium text-foreground">OpenClaw / ClawHub</p>
						<p className="mt-2">
							Local starter pack is first-cut and the ClawHub package template
							is publish-ready, but a live publish receipt is still missing.
						</p>
					</div>
					<div className="rounded-lg border border-border/60 bg-muted/20 p-4">
						<p className="font-medium text-foreground">Official MCP Registry</p>
						<p className="mt-2">
							The registry template is metadata-ready. Real publication still
							needs install-artifact and namespace proof.
						</p>
					</div>
				</CardContent>
			</Card>

			<Card className="folo-surface border-border/70">
				<CardHeader>
					<CardTitle>
						Plugin-grade bundles and official-surface templates
					</CardTitle>
					<CardDescription>
						These are the concrete distribution artifacts behind today&apos;s
						builder story.
					</CardDescription>
				</CardHeader>
				<CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
					<Button asChild variant="outline" size="sm">
						<a
							href={RESOURCE_LINKS.codexBundle}
							target="_blank"
							rel="noreferrer"
						>
							Inspect Codex bundle
						</a>
					</Button>
					<Button asChild variant="outline" size="sm">
						<a
							href={RESOURCE_LINKS.claudeBundle}
							target="_blank"
							rel="noreferrer"
						>
							Inspect Claude bundle
						</a>
					</Button>
					<Button asChild variant="outline" size="sm">
						<a
							href={RESOURCE_LINKS.openclawBundle}
							target="_blank"
							rel="noreferrer"
						>
							Inspect OpenClaw pack
						</a>
					</Button>
					<Button asChild variant="outline" size="sm">
						<a
							href={RESOURCE_LINKS.mcpRegistry}
							target="_blank"
							rel="noreferrer"
						>
							Inspect MCP registry template
						</a>
					</Button>
				</CardContent>
			</Card>

			<Card className="folo-surface border-border/70">
				<CardHeader>
					<CardTitle>Official-surface status board</CardTitle>
					<CardDescription>
						Use this board when you need the honest answer to: what already
						exists, what is still submission-ready, and what still needs a real
						listing receipt before anyone can call it live.
					</CardDescription>
				</CardHeader>
				<CardContent className="grid gap-4 lg:grid-cols-2">
					{OFFICIAL_SURFACE_ROWS.map((item) => (
						<div
							key={item.name}
							className="rounded-lg border border-border/60 bg-muted/20 p-4"
						>
							<div className="flex flex-wrap items-center gap-2">
								<p className="font-medium text-foreground">{item.name}</p>
								<Badge variant={item.tone}>{item.status}</Badge>
							</div>
							<p className="mt-3 text-sm text-muted-foreground">
								{item.summary}
							</p>
							<div className="mt-4 flex flex-wrap gap-3">
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

			<section className="grid gap-4 lg:grid-cols-[1.1fr_1fr]">
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<CardTitle>What still needs live submission proof</CardTitle>
						<CardDescription>
							The repo now has real bundles, templates, and starter packs. The
							next bar is no longer “write another README”, but “show a real
							submission, listing, pending-review URL, or exact external
							blocker.”
						</CardDescription>
					</CardHeader>
					<CardContent className="space-y-3 text-sm text-muted-foreground">
						<p>
							Start from the package or template that already exists, then keep
							one ledger per platform:
						</p>
						<ul className="list-disc space-y-2 pl-5">
							<li>submission artifact</li>
							<li>listing or review URL</li>
							<li>pending-review or receipt proof</li>
							<li>exact blocker when the platform still needs a human step</li>
						</ul>
						<div className="flex flex-wrap gap-3">
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
					</CardContent>
				</Card>

				<Card className="folo-surface border-border/70">
					<CardHeader>
						<CardTitle>Human-only finish line</CardTitle>
						<CardDescription>
							Keep the automation boundary honest. Repo-side engineering and
							package prep can keep moving; these last-mile steps should only
							move when a human must really click or confirm.
						</CardDescription>
					</CardHeader>
					<CardContent className="space-y-2 text-sm text-muted-foreground">
						{HUMAN_ONLY_STEPS.map((item) => (
							<p key={item}>{item}</p>
						))}
					</CardContent>
				</Card>
			</section>
		</div>
	);
}
