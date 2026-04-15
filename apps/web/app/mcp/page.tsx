import type { Metadata } from "next";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { getLocaleMessages } from "@/lib/i18n/messages";
import { buildProductMetadata } from "@/lib/seo";

const mcpCopy = getLocaleMessages().mcpPage;

export const metadata: Metadata = buildProductMetadata({
	title: mcpCopy.metadataTitle,
	description: mcpCopy.metadataDescription,
	route: "mcp",
});

const TOOL_EXAMPLES = [
	"sourceharbor.jobs.get",
	"sourceharbor.jobs.compare",
	"sourceharbor.knowledge.cards.list",
	"sourceharbor.retrieval.search",
	"sourceharbor.ingest.poll",
];

export default function McpPage() {
	const copy = getLocaleMessages().mcpPage;
	return (
		<div className="folo-page-shell folo-unified-shell">
			<div className="folo-page-header">
				<p className="folo-page-kicker">{copy.kicker}</p>
				<h1 className="folo-page-title" data-route-heading tabIndex={-1}>
					{copy.heroTitle}
				</h1>
				<p className="folo-page-subtitle">{copy.heroSubtitle}</p>
			</div>

			<section className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<h2 className="text-xl font-semibold">{copy.startTitle}</h2>
						<CardDescription>
							Open this only when you already know you need tool calls, not a
							reading surface.
						</CardDescription>
					</CardHeader>
					<CardContent className="space-y-4">
						<pre className="overflow-x-auto rounded-lg border border-border/70 bg-muted/40 p-4 text-sm">
							<code>{`./bin/sourceharbor help
./bin/sourceharbor mcp

# direct entrypoint still works
./bin/dev-mcp`}</code>
						</pre>
						<p className="text-sm text-muted-foreground">
							Keep MCP behind the reader-facing pages. This is a tool door, not
							the main front door.
						</p>
						<p className="text-sm leading-7 text-muted-foreground">
							Start the server, try one tool family, then leave this page once you know the call you need.
						</p>
					</CardContent>
				</Card>
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<h2 className="text-xl font-semibold">Start with one tool family</h2>
						<CardDescription>
							Jobs, retrieval, and ingest are enough to prove the lane. You do
							not need the whole list on day one.
						</CardDescription>
					</CardHeader>
					<CardContent className="space-y-4">
						<div className="flex flex-wrap gap-2">
							{TOOL_EXAMPLES.map((tool) => (
								<Badge
									key={tool}
									variant="outline"
									className="bg-background/70 font-normal"
								>
									<code>{tool}</code>
								</Badge>
							))}
						</div>
						<div className="rounded-2xl border border-border/60 bg-background/60 p-4 text-sm text-muted-foreground">
							<p className="font-medium text-foreground">
								Use MCP for tool calls, not for storytelling
							</p>
							<p className="mt-2">
								Start with jobs, retrieval, or ingest. Save the bigger answer layer for Search or Ask when a human needs to read the outcome.
							</p>
						</div>
					</CardContent>
				</Card>
			</section>

			<Card className="folo-surface border-border/70">
				<CardHeader>
					<CardTitle>When to stay here</CardTitle>
					<CardDescription>
						MCP is for agents and builders. Search and Ask stay better for
						humans who want something readable.
					</CardDescription>
				</CardHeader>
				<CardContent className="grid gap-3 text-sm text-muted-foreground md:grid-cols-3">
					<div className="rounded-2xl border border-border/60 bg-muted/20 p-4">
						<p className="font-medium text-foreground">MCP</p>
						<p className="mt-2">
							Stay here when you already know the tool family and just need exact calls against the live pipeline.
						</p>
					</div>
					<div className="rounded-2xl border border-border/60 bg-muted/20 p-4">
						<p className="font-medium text-foreground">Search</p>
						<p className="mt-2">
							Use Search when a human needs grounded retrieval results laid out instead of raw tool output.
						</p>
						<p className="mt-3 text-sm text-muted-foreground">
							<Link
								href="/search"
								className="underline underline-offset-4 hover:text-foreground"
							>
								{copy.searchCta}
							</Link>
						</p>
					</div>
					<div className="rounded-2xl border border-border/60 bg-muted/20 p-4">
						<p className="font-medium text-foreground">Ask</p>
						<p className="mt-2">
							Use Ask when the same evidence needs to become an answer, change summary, or story-aware explanation.
						</p>
						<p className="mt-3 text-sm text-muted-foreground">
							<Link
								href="/ask"
								className="underline underline-offset-4 hover:text-foreground"
							>
								{copy.askCta}
							</Link>
						</p>
					</div>
				</CardContent>
			</Card>
		</div>
	);
}
