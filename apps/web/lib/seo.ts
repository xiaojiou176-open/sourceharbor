import type { Metadata } from "next";

type SeoRoute =
	| "dashboard"
	| "ops"
	| "settings"
	| "builders"
	| "mcp"
	| "knowledge"
	| "ingestRuns"
	| "feed"
	| "subscriptions"
	| "reader"
	| "search"
	| "ask"
	| "watchlists"
	| "trends"
	| "briefings"
	| "proof"
	| "playground"
	| "jobs"
	| "useCases";

const CORE_KEYWORDS = [
	"SourceHarbor",
	"reader-first source intelligence",
	"AI knowledge pipeline",
	"source-first AI workflow",
	"source-universe intake",
	"published reader documents",
	"grounded retrieval",
	"evidence bundle",
	"MCP server",
	"Model Context Protocol",
	"agentic coding workflow",
	"AI coding agent",
	"Codex workflow",
	"Codex MCP server",
	"Claude Code workflow",
	"Claude Code MCP server",
];

const ROUTE_PATHS: Record<SeoRoute, string> = {
	dashboard: "/",
	ops: "/ops",
	settings: "/settings",
	builders: "/builders",
	mcp: "/mcp",
	knowledge: "/knowledge",
	ingestRuns: "/ingest-runs",
	feed: "/feed",
	subscriptions: "/subscriptions",
	reader: "/reader",
	search: "/search",
	ask: "/ask",
	watchlists: "/watchlists",
	trends: "/trends",
	briefings: "/briefings",
	proof: "/proof",
	playground: "/playground",
	jobs: "/jobs",
	useCases: "/use-cases",
};

const DEFAULT_SOCIAL_PREVIEW_IMAGE =
	"https://raw.githubusercontent.com/xiaojiou176-open/sourceharbor/main/docs/assets/sourceharbor-social-preview.png";

const ROUTE_KEYWORDS: Record<SeoRoute, string[]> = {
	dashboard: [
		"reader-first front door",
		"knowledge intake",
		"digest feed",
		"published reader documents",
		"builder entry",
		"AI developer tooling",
	],
	ops: [
		"Ops inbox",
		"delivery readiness",
		"provider health",
		"AI workflow triage",
	],
	settings: [
		"notification delivery",
		"alert configuration",
		"daily digest settings",
	],
	builders: [
		"builder first hop",
		"plugin bundle",
		"Codex plugin bundle",
		"Claude Code plugin bundle",
		"MCP registry template",
	],
	mcp: [
		"MCP quickstart",
		"agent control plane",
		"Codex MCP",
		"Claude Code MCP",
		"agentic coding control plane",
	],
	knowledge: ["knowledge cards", "AI research memory", "job-linked evidence"],
	ingestRuns: ["ingest ledger", "source intake", "pipeline intake trace"],
	feed: [
		"digest feed",
		"reading flow",
		"AI digest review",
		"operator reading pane",
	],
	subscriptions: [
		"source subscriptions",
		"source intake settings",
		"subscription control plane",
		"ingestion sources",
	],
	reader: [
		"reader frontstage",
		"published reader documents",
		"yellow warning reading surface",
		"source contribution drawer",
	],
	search: [
		"grounded search",
		"Ask your sources",
		"retrieval API",
		"citation-first AI",
		"AI search for source artifacts",
	],
	ask: [
		"briefing-aware Ask",
		"watchlist question front door",
		"answer change evidence",
		"grounded answer workflow",
	],
	watchlists: [
		"AI trend watchlist",
		"tracking object",
		"Codex updates tracking",
		"Claude Code tracking",
		"compounder workflow",
	],
	trends: [
		"compounder front door",
		"cross-run trend",
		"topic diff",
		"claim change tracking",
		"AI workflow trend",
	],
	briefings: [
		"watchlist briefing",
		"shared story surface",
		"unified information surface",
		"cross-source briefing",
		"evidence drill-down",
	],
	proof: [
		"proof boundary",
		"runtime proof",
		"local supervisor proof",
		"release readiness",
	],
	playground: ["sample playground", "demo corpus", "evidence bundle example"],
	jobs: ["job trace", "pipeline trace", "run compare", "artifact index"],
	useCases: [
		"AI research pipeline",
		"builder workflow",
		"Codex use case",
		"Claude Code use case",
		"AI coding workflow",
	],
};

function dedupeKeywords(keywords: string[]): string[] {
	return [...new Set(keywords.map((item) => item.trim()).filter(Boolean))];
}

function resolvePublicSiteUrl(): URL | undefined {
	const candidate = process.env.SOURCE_HARBOR_PUBLIC_SITE_URL?.trim() || "";
	if (!candidate) {
		return undefined;
	}
	try {
		return new URL(candidate.endsWith("/") ? candidate : `${candidate}/`);
	} catch {
		return undefined;
	}
}

function resolveSocialPreviewImage(): string {
	return DEFAULT_SOCIAL_PREVIEW_IMAGE;
}

function buildCanonical(
	pathname: string,
	siteUrl: URL | undefined,
): string | undefined {
	if (!siteUrl) {
		return undefined;
	}
	return new URL(pathname, siteUrl).toString();
}

export function buildAppShellMetadata(): Metadata {
	const siteUrl = resolvePublicSiteUrl();
	const canonical = buildCanonical("/", siteUrl);
	const socialPreviewImage = resolveSocialPreviewImage();
	return {
		title: {
			default: "SourceHarbor Front Door",
			template: "%s | SourceHarbor",
		},
		metadataBase: siteUrl,
		applicationName: "SourceHarbor",
		description:
			"Reader-first front door for source-universe intake, digest curation, published reader documents, and builder entry through MCP and HTTP API.",
		keywords: dedupeKeywords([
			...CORE_KEYWORDS,
			...ROUTE_KEYWORDS.dashboard,
			"job trace",
			"evidence bundle",
		]),
		alternates: canonical ? { canonical } : undefined,
		robots: {
			index: true,
			follow: true,
		},
		openGraph: {
			title: "SourceHarbor Front Door",
			description:
				"Reader-first front door for source-universe intake, digest curation, published reader documents, and builder entry through MCP and HTTP API.",
			type: "website",
			siteName: "SourceHarbor",
			url: canonical,
			images: [
				{
					url: socialPreviewImage,
					width: 1200,
					height: 630,
					alt: "SourceHarbor social preview",
				},
			],
		},
		twitter: {
			card: "summary_large_image",
			title: "SourceHarbor Front Door",
			description:
				"Reader-first front door for source-universe intake, digest curation, published reader documents, and builder entry through MCP and HTTP API.",
			images: [socialPreviewImage],
		},
	};
}

export function buildProductMetadata({
	title,
	description,
	route,
	keywords = [],
	pathname,
}: {
	title: string;
	description?: string;
	route: SeoRoute;
	keywords?: string[];
	pathname?: string;
}): Metadata {
	const mergedKeywords = dedupeKeywords([
		...CORE_KEYWORDS,
		...ROUTE_KEYWORDS[route],
		...keywords,
	]);
	const siteUrl = resolvePublicSiteUrl();
	const canonical = buildCanonical(pathname ?? ROUTE_PATHS[route], siteUrl);
	const socialPreviewImage = resolveSocialPreviewImage();

	return {
		title,
		description,
		metadataBase: siteUrl,
		applicationName: "SourceHarbor",
		keywords: mergedKeywords,
		category: "software",
		alternates: canonical ? { canonical } : undefined,
		robots: {
			index: true,
			follow: true,
		},
		openGraph: {
			title,
			description,
			type: "website",
			siteName: "SourceHarbor",
			url: canonical,
			images: [
				{
					url: socialPreviewImage,
					width: 1200,
					height: 630,
					alt: "SourceHarbor social preview",
				},
			],
		},
		twitter: {
			card: "summary_large_image",
			title,
			description,
			images: [socialPreviewImage],
		},
	};
}
