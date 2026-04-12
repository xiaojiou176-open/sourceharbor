import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { USE_CASE_PAGES, type UseCaseSlug } from "@/lib/demo-content";
import { getLocaleMessages } from "@/lib/i18n/messages";
import { buildProductMetadata } from "@/lib/seo";

const BUILDER_RESOURCE_LINKS = {
	builders: "/builders",
	proof: "/proof",
	starterPacks:
		"https://github.com/xiaojiou176-open/sourceharbor/blob/main/starter-packs/README.md",
	cli: "https://github.com/xiaojiou176-open/sourceharbor/blob/main/packages/sourceharbor-cli/README.md",
	sdk: "https://github.com/xiaojiou176-open/sourceharbor/blob/main/packages/sourceharbor-sdk/README.md",
	mediaKit:
		"https://github.com/xiaojiou176-open/sourceharbor/blob/main/docs/media-kit.md",
} as const;

type UseCasePageProps = {
	params: Promise<{ slug: string }> | { slug: string };
};

export async function generateStaticParams() {
	return Object.keys(USE_CASE_PAGES).map((slug) => ({ slug }));
}

export async function generateMetadata({
	params,
}: UseCasePageProps): Promise<Metadata> {
	const { slug } = await Promise.resolve(params);
	const content = USE_CASE_PAGES[slug as UseCaseSlug];
	if (!content) {
		return {};
	}
	const extraKeywords: Partial<Record<UseCaseSlug, string[]>> = {
		youtube: ["YouTube AI digest", "video to knowledge workflow"],
		bilibili: ["Bilibili knowledge pipeline", "video research workflow"],
		rss: ["RSS research pipeline", "source-first research intake"],
		"mcp-use-cases": ["MCP use cases", "Model Context Protocol workflow"],
		codex: ["Codex workflow", "Codex MCP workflow"],
		"claude-code": ["Claude Code workflow", "Claude Code MCP"],
		"research-pipeline": ["AI research pipeline", "watchlists and trends"],
	};
	return {
		...buildProductMetadata({
			title: content.title,
			description: content.subtitle,
			route: "useCases",
			pathname: `/use-cases/${slug}`,
			keywords: extraKeywords[slug as UseCaseSlug] ?? [],
		}),
	};
}

export default async function UseCasePage({ params }: UseCasePageProps) {
	const { slug } = await Promise.resolve(params);
	const content = USE_CASE_PAGES[slug as UseCaseSlug];
	const copy = getLocaleMessages().useCasesPage;
	const builderCopy = getLocaleMessages().builderSurfaces;
	const builderResourceLinks = [
		{
			href: BUILDER_RESOURCE_LINKS.builders,
			label: builderCopy.buildersGuideCta,
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
	if (!content) {
		notFound();
	}

	return (
		<div className="folo-page-shell folo-unified-shell">
			<div className="folo-page-header">
				<p className="folo-page-kicker">{copy.kicker}</p>
				<h1 className="folo-page-title" data-route-heading tabIndex={-1}>
					{content.title}
				</h1>
				<p className="folo-page-subtitle">{content.subtitle}</p>
			</div>

			<Card className="folo-surface border-border/70">
				<CardHeader>
					<CardTitle>{copy.whyTitle}</CardTitle>
					<CardDescription>{copy.whyDescription}</CardDescription>
				</CardHeader>
				<CardContent className="space-y-3 text-sm text-muted-foreground">
					{content.why.map((item) => (
						<p key={item}>{item}</p>
					))}
				</CardContent>
			</Card>

			<Card className="folo-surface border-border/70">
				<CardHeader>
					<CardTitle>{copy.nextStepsTitle}</CardTitle>
					<CardDescription>{copy.nextStepsDescription}</CardDescription>
				</CardHeader>
				<CardContent className="flex flex-wrap gap-3">
					{content.links.map((item) => (
						<Button key={item.href} asChild variant="outline" size="sm">
							{item.href.startsWith("http") ? (
								<a href={item.href} target="_blank" rel="noreferrer">
									{item.label}
								</a>
							) : (
								<Link href={item.href}>{item.label}</Link>
							)}
						</Button>
					))}
					<Button asChild variant="ghost" size="sm">
						<Link href={BUILDER_RESOURCE_LINKS.proof}>{copy.proofCta}</Link>
					</Button>
				</CardContent>
			</Card>

			<Card className="folo-surface border-border/70">
				<CardHeader>
					<CardTitle>Current action path</CardTitle>
					<CardDescription>
						Start from the live compounder front door, then use sample surfaces
						only when you want a clearly labeled demo path.
					</CardDescription>
				</CardHeader>
				<CardContent className="grid gap-3 text-sm text-muted-foreground md:grid-cols-3">
					<div className="rounded-lg border border-border/60 bg-muted/20 p-4">
						<p className="font-medium text-foreground">1. Live tracking</p>
						<p className="mt-2">
							Use <code>/watchlists</code> when you want a durable object for
							what to track.
						</p>
					</div>
					<div className="rounded-lg border border-border/60 bg-muted/20 p-4">
						<p className="font-medium text-foreground">2. Unified view</p>
						<p className="mt-2">
							Use <code>/trends</code> to see the current repeated story, recent
							movement, and drill-down evidence.
						</p>
					</div>
					<div className="rounded-lg border border-border/60 bg-muted/20 p-4">
						<p className="font-medium text-foreground">3. Sample proof</p>
						<p className="mt-2">
							Use <code>/playground</code> only for sample/demo proof, not for
							live operator state.
						</p>
					</div>
				</CardContent>
			</Card>

			<Card className="folo-surface border-border/70">
				<CardHeader>
					<CardTitle>{copy.builderTitle}</CardTitle>
					<CardDescription>{copy.builderDescription}</CardDescription>
				</CardHeader>
				<CardContent className="flex flex-wrap gap-3">
					<Button asChild variant="outline" size="sm">
						<Link href="/mcp">{builderCopy.mcpCta}</Link>
					</Button>
					<Button asChild variant="outline" size="sm">
						<Link href="/use-cases/codex">{builderCopy.codexCta}</Link>
					</Button>
					<Button asChild variant="outline" size="sm">
						<Link href="/use-cases/claude-code">
							{builderCopy.claudeCodeCta}
						</Link>
					</Button>
					{builderResourceLinks.map((item) => (
						<Button key={item.href} asChild variant="ghost" size="sm">
							{item.href.startsWith("http") ? (
								<a href={item.href} target="_blank" rel="noreferrer">
									{item.label}
								</a>
							) : (
								<Link href={item.href}>{item.label}</Link>
							)}
						</Button>
					))}
				</CardContent>
			</Card>
		</div>
	);
}
