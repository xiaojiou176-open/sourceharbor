export const USE_CASE_PAGES = {
	youtube: {
		title: "YouTube to AI digest",
		subtitle:
			"Turn long YouTube videos into grounded digests, searchable knowledge, and shareable evidence bundles.",
		why: [
			"Use SourceHarbor when you want a YouTube source to become a digest, not just a transcript blob.",
			"Job trace and evidence bundle keep the output reviewable instead of turning it into black-box AI copy.",
		],
		links: [
			{ href: "/trends", label: "Open compounder front door" },
			{ href: "/watchlists", label: "Open Watchlists" },
			{ href: "/playground", label: "Open sample playground" },
			{
				href: "https://github.com/xiaojiou176-open/sourceharbor/blob/main/docs/start-here.md",
				label: "Read local quickstart",
			},
		],
	},
	bilibili: {
		title: "Bilibili to knowledge base",
		subtitle:
			"Turn Bilibili sources into digests, knowledge cards, and repeatable research assets.",
		why: [
			"Use the same pipeline for Bilibili instead of building a separate notes workflow by hand.",
			"Knowledge cards and trends help you come back to the same source family over time.",
		],
		links: [
			{ href: "/trends", label: "Open compounder front door" },
			{ href: "/knowledge", label: "Open Knowledge" },
			{ href: "/watchlists", label: "Open Watchlists" },
			{ href: "/playground", label: "Open sample playground" },
		],
	},
	rss: {
		title: "RSS to AI research pipeline",
		subtitle:
			"Turn RSS intake into a research feed, topic tracking, and MCP-ready operator workflow.",
		why: [
			"RSS is not just another source type; it is the fastest path into repeatable research intake.",
			"Feed, watchlists, trends, and ops diagnostics help you keep returning to the same research stream.",
		],
		links: [
			{ href: "/feed", label: "Open Feed" },
			{ href: "/watchlists", label: "Open Watchlists" },
			{ href: "/trends", label: "Open Trends" },
			{ href: "/ops", label: "Open Ops inbox" },
		],
	},
	"mcp-use-cases": {
		title: "MCP use cases",
		subtitle:
			"Use the same SourceHarbor pipeline from assistants, MCP clients, and operator workflows without duplicating business logic.",
		why: [
			"MCP is the agent-facing doorway into the same system state used by Web and API.",
			"Use cases are strongest when grounded in real jobs, retrieval, and evidence bundles.",
		],
		links: [
			{ href: "/trends", label: "Open compounder front door" },
			{ href: "/mcp", label: "Open MCP quickstart" },
			{ href: "/search", label: "Open Search" },
			{ href: "/playground", label: "Open sample playground" },
		],
	},
	codex: {
		title: "Codex operator workflow",
		subtitle:
			"Use SourceHarbor from Codex through MCP or HTTP without duplicating the product's operator truth.",
		why: [
			"Codex is a strong fit when you want a coding or ops agent to inspect real jobs, artifacts, retrieval results, and readiness gates instead of scraping screenshots.",
			"SourceHarbor already exposes the same state to Web, API, and MCP, so Codex can stay on the real control plane.",
		],
		links: [
			{ href: "/mcp", label: "Open MCP quickstart" },
			{ href: "/trends", label: "Open compounder front door" },
			{ href: "/ops", label: "Open Ops inbox" },
			{ href: "/search", label: "Open Search" },
		],
	},
	"claude-code": {
		title: "Claude Code workflow",
		subtitle:
			"Use SourceHarbor as a source-first MCP and API substrate for Claude Code-style local workflows.",
		why: [
			"Claude Code is a better fit than a generic chat shell because SourceHarbor already has inspectable jobs, artifacts, retrieval, and operator surfaces.",
			"The honest story is not 'another assistant'; it is a reusable AI knowledge runtime that Claude Code can query through governed surfaces.",
		],
		links: [
			{ href: "/mcp", label: "Open MCP quickstart" },
			{ href: "/trends", label: "Open compounder front door" },
			{
				href: "/use-cases/research-pipeline",
				label: "Open research pipeline use case",
			},
			{ href: "/playground", label: "Open sample playground" },
		],
	},
	"research-pipeline": {
		title: "AI research pipeline",
		subtitle:
			"See how SourceHarbor connects intake, digest generation, search, watchlists, trends, and evidence bundles into one reusable loop.",
		why: [
			"SourceHarbor is strongest when reused over time, not when treated like a one-shot summarizer.",
			"This page is a truthful map of the current compounder layer, not a hosted product promise.",
		],
		links: [
			{ href: "/trends", label: "Open compounder front door" },
			{ href: "/watchlists", label: "Open Watchlists" },
			{ href: "/playground", label: "Open sample playground" },
		],
	},
} as const;

export type UseCaseSlug = keyof typeof USE_CASE_PAGES;
