import type { Metadata } from "next";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
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
						<CardDescription>{copy.startDescription}</CardDescription>
					</CardHeader>
					<CardContent className="space-y-4">
						<pre className="overflow-x-auto rounded-lg border border-border/70 bg-muted/40 p-4 text-sm">
							<code>{`./bin/sourceharbor help
./bin/sourceharbor mcp

# direct entrypoint still works
./bin/dev-mcp`}</code>
						</pre>
						<p className="text-sm text-muted-foreground">{copy.startNote}</p>
					</CardContent>
				</Card>
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<h2 className="text-xl font-semibold">{copy.toolsTitle}</h2>
						<CardDescription>{copy.toolsDescription}</CardDescription>
					</CardHeader>
					<CardContent className="space-y-2">
						<ul className="list-disc space-y-2 pl-5 text-sm text-muted-foreground">
							{TOOL_EXAMPLES.map((tool) => (
								<li key={tool}>
									<code>{tool}</code>
								</li>
							))}
						</ul>
					</CardContent>
				</Card>
			</section>

			<Card className="folo-surface border-border/70">
				<CardHeader>
					<h2 className="text-xl font-semibold">{copy.relationshipTitle}</h2>
				</CardHeader>
				<CardContent className="space-y-3 text-sm text-muted-foreground">
					<p>{copy.relationshipDescription}</p>
					<div className="flex flex-wrap gap-3">
						<Button asChild variant="outline" size="sm">
							<Link href="/search">{copy.searchCta}</Link>
						</Button>
						<Button asChild variant="outline" size="sm">
							<Link href="/ask">{copy.askCta}</Link>
						</Button>
					</div>
				</CardContent>
			</Card>
		</div>
	);
}
