import { describe, expect, it } from "vitest";

import { metadata as askMetadata } from "@/app/ask/page";
import { metadata as briefingsMetadata } from "@/app/briefings/page";
import { metadata as buildersMetadata } from "@/app/builders/page";
import { metadata as feedMetadata } from "@/app/feed/page";
import { metadata as jobsMetadata } from "@/app/jobs/page";
import { metadata as mcpMetadata } from "@/app/mcp/page";
import { metadata as playgroundMetadata } from "@/app/playground/page";
import { metadata as proofMetadata } from "@/app/proof/page";
import { metadata as searchMetadata } from "@/app/search/page";
import { metadata as subscriptionsMetadata } from "@/app/subscriptions/page";
import { metadata as trendsMetadata } from "@/app/trends/page";
import { generateMetadata as generateUseCaseMetadata } from "@/app/use-cases/[slug]/page";
import { metadata as watchlistsMetadata } from "@/app/watchlists/page";
import { buildAppShellMetadata, buildProductMetadata } from "@/lib/seo";

function toKeywordList(value: unknown): string[] {
	if (Array.isArray(value)) {
		return value.filter((item): item is string => typeof item === "string");
	}
	if (typeof value === "string") {
		return value
			.split(",")
			.map((item) => item.trim())
			.filter(Boolean);
	}
	return [];
}

describe("route metadata", () => {
	it("keeps app-shell metadata aligned to the reader-first front-door story", () => {
		const metadata = buildAppShellMetadata();

		expect(metadata.title).toMatchObject({
			default: "SourceHarbor Front Door",
		});
		expect(metadata.description).toMatch(/Reader-first front door/i);
		expect(toKeywordList(metadata.keywords)).toEqual(
			expect.arrayContaining([
				"reader-first source intelligence",
				"source-universe intake",
				"published reader documents",
				"MCP server",
				"AI coding agent",
				"agentic coding workflow",
				"Codex workflow",
				"Codex MCP server",
				"Claude Code workflow",
				"Claude Code MCP server",
				"job trace",
				"evidence bundle",
			]),
		);
		expect(metadata.applicationName).toBe("SourceHarbor");
		expect(metadata.openGraph?.siteName).toBe("SourceHarbor");
		expect(metadata.openGraph?.images).toEqual(
			expect.arrayContaining([
				expect.objectContaining({
					url: expect.stringContaining("sourceharbor-social-preview"),
				}),
			]),
		);
		expect(metadata.twitter?.images).toEqual(
			expect.arrayContaining([
				expect.stringContaining("sourceharbor-social-preview"),
			]),
		);
	});

	it("adds canonical metadata when a public site URL is configured", () => {
		process.env.SOURCE_HARBOR_PUBLIC_SITE_URL = "https://sourceharbor.ai";

		const metadata = buildProductMetadata({
			title: "Search",
			description: "Grounded search for SourceHarbor artifacts.",
			route: "search",
		});

		expect(metadata.metadataBase?.toString()).toBe("https://sourceharbor.ai/");
		expect(metadata.alternates?.canonical).toBe(
			"https://sourceharbor.ai/search",
		);
		expect(metadata.openGraph?.url).toBe("https://sourceharbor.ai/search");
		expect(metadata.openGraph?.images).toEqual(
			expect.arrayContaining([
				expect.objectContaining({
					url: "https://raw.githubusercontent.com/xiaojiou176-open/sourceharbor/main/docs/assets/sourceharbor-social-preview.png",
				}),
			]),
		);

		delete process.env.SOURCE_HARBOR_PUBLIC_SITE_URL;
	});

	it("keeps dynamic use-case metadata on the slug-specific canonical path", async () => {
		process.env.SOURCE_HARBOR_PUBLIC_SITE_URL = "https://sourceharbor.ai";

		const metadata = await generateUseCaseMetadata({
			params: Promise.resolve({ slug: "claude-code" }),
		});

		expect(metadata.alternates?.canonical).toBe(
			"https://sourceharbor.ai/use-cases/claude-code",
		);
		expect(metadata.openGraph?.url).toBe(
			"https://sourceharbor.ai/use-cases/claude-code",
		);

		delete process.env.SOURCE_HARBOR_PUBLIC_SITE_URL;
	});

	it("keeps search and ask metadata grounded, retrieval-first, and keyword-rich", () => {
		expect(searchMetadata.title).toBe("Search");
		expect(searchMetadata.description).toMatch(/Grounded search/i);
		expect(toKeywordList(searchMetadata.keywords)).toEqual(
			expect.arrayContaining([
				"grounded search",
				"retrieval API",
				"citation-first AI",
				"AI search for source artifacts",
				"Codex workflow",
				"Claude Code workflow",
			]),
		);

		expect(askMetadata.title).toBe("Ask your sources");
		expect(askMetadata.description).toMatch(/briefing-backed Ask front door/i);
		expect(toKeywordList(askMetadata.keywords)).toEqual(
			expect.arrayContaining([
				"briefing-aware Ask",
				"watchlist question front door",
				"answer change evidence workflow",
				"grounded answer workflow",
			]),
		);
	});

	it("keeps MCP/feed/subscriptions metadata on the same product line", () => {
		expect(buildersMetadata.title).toBe("Builders");
		expect(buildersMetadata.description).toMatch(/builder first hop/i);
		expect(toKeywordList(buildersMetadata.keywords)).toEqual(
			expect.arrayContaining([
				"builder first hop",
				"plugin bundle",
				"Codex plugin bundle",
				"Claude Code plugin bundle",
				"MCP registry template",
			]),
		);

		expect(mcpMetadata.title).toBe("MCP");
		expect(mcpMetadata.description).toMatch(/MCP quickstart/i);
		expect(toKeywordList(mcpMetadata.keywords)).toEqual(
			expect.arrayContaining([
				"MCP quickstart",
				"Codex MCP",
				"Claude Code MCP",
				"agentic coding control plane",
			]),
		);

		expect(feedMetadata.title).toBe("Digest Feed");
		expect(feedMetadata.description).toMatch(/digest feed/i);
		expect(toKeywordList(feedMetadata.keywords)).toEqual(
			expect.arrayContaining([
				"digest feed",
				"reading flow",
				"operator reading pane",
			]),
		);

		expect(subscriptionsMetadata.title).toBe("Subscriptions");
		expect(subscriptionsMetadata.description).toMatch(/subscription/i);
		expect(toKeywordList(subscriptionsMetadata.keywords)).toEqual(
			expect.arrayContaining([
				"source subscriptions",
				"source intake settings",
				"subscription control plane",
			]),
		);
	});

	it("keeps use-case metadata ready for promised params and ecosystem keywords", async () => {
		const metadata = await generateUseCaseMetadata({
			params: Promise.resolve({ slug: "claude-code" }),
		});

		expect(metadata.title).toBe("Claude Code workflow");
		expect(metadata.description).toMatch(/Claude Code-style local workflows/i);
		expect(toKeywordList(metadata.keywords)).toEqual(
			expect.arrayContaining([
				"Claude Code workflow",
				"Claude Code MCP",
				"Codex workflow",
				"AI coding workflow",
				"AI research pipeline",
			]),
		);
	});

	it("keeps compounder and proof metadata aligned to the reusable control-tower story", () => {
		expect(watchlistsMetadata.title).toBe("Watchlists");
		expect(watchlistsMetadata.description).toMatch(/watchlists/i);
		expect(toKeywordList(watchlistsMetadata.keywords)).toEqual(
			expect.arrayContaining([
				"AI trend watchlist",
				"Codex updates tracking",
				"Claude Code tracking",
			]),
		);

		expect(trendsMetadata.title).toBe("Trends");
		expect(trendsMetadata.description).toMatch(/Cross-run trend/i);
		expect(toKeywordList(trendsMetadata.keywords)).toEqual(
			expect.arrayContaining([
				"cross-run trend",
				"topic diff",
				"AI workflow trend",
			]),
		);

		expect(briefingsMetadata.title).toBe("Briefings");
		expect(briefingsMetadata.description).toMatch(
			/Unified watchlist briefing/i,
		);
		expect(toKeywordList(briefingsMetadata.keywords)).toEqual(
			expect.arrayContaining([
				"watchlist briefing",
				"unified information surface",
				"cross-source briefing",
				"evidence drill-down",
			]),
		);

		expect(proofMetadata.title).toBe("Proof");
		expect(proofMetadata.description).toMatch(/proof boundary/i);
		expect(toKeywordList(proofMetadata.keywords)).toEqual(
			expect.arrayContaining([
				"proof boundary",
				"local supervisor proof",
				"release readiness",
			]),
		);

		expect(playgroundMetadata.title).toBe("Playground");
		expect(playgroundMetadata.description).toMatch(/sample corpus/i);
		expect(toKeywordList(playgroundMetadata.keywords)).toEqual(
			expect.arrayContaining([
				"sample playground",
				"demo corpus",
				"evidence bundle example",
			]),
		);

		expect(jobsMetadata.title).toBe("Job Trace");
		expect(jobsMetadata.description).toMatch(/job trace/i);
		expect(toKeywordList(jobsMetadata.keywords)).toEqual(
			expect.arrayContaining(["job trace", "pipeline trace", "artifact index"]),
		);
	});
});
