import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import path from "node:path";

import type { Metadata } from "next";
import Link from "next/link";

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

const playgroundCopy = getLocaleMessages().playgroundPage;

export const metadata: Metadata = buildProductMetadata({
	title: playgroundCopy.metadataTitle,
	description: playgroundCopy.metadataDescription,
	route: "playground",
});

async function loadSampleCorpus() {
	const configuredRoot = process.env.SOURCE_HARBOR_REPO_ROOT?.trim();
	const candidates = new Set<string>();
	if (configuredRoot) {
		candidates.add(configuredRoot);
	}
	let current = path.resolve(process.cwd());
	for (let index = 0; index < 8; index += 1) {
		candidates.add(current);
		current = path.dirname(current);
	}
	const candidateList = [...candidates];

	const filePath =
		candidateList
			.map((root) =>
				path.join(root, "docs/samples/sourceharbor-demo-corpus.json"),
			)
			.find((candidate) => existsSync(candidate)) ??
		path.join(candidateList[0], "docs/samples/sourceharbor-demo-corpus.json");
	return JSON.parse(await readFile(filePath, "utf-8")) as {
		label: string;
		description: string;
		sources: Array<{ platform: string; title: string; url: string }>;
		example_jobs: Array<{
			job_id: string;
			platform: string;
			title: string;
			pipeline_final_status: string;
			digest_excerpt: string;
		}>;
		example_retrieval_results: Array<{
			query: string;
			source: string;
			snippet: string;
			job_id: string;
		}>;
		example_watchlists: Array<{
			name: string;
			matcher_type: string;
			matcher_value: string;
		}>;
		example_trend: {
			watchlist_name: string;
			recent_runs: Array<{
				job_id: string;
				added_topics: string[];
				removed_topics: string[];
				added_claim_kinds: string[];
				removed_claim_kinds: string[];
			}>;
		};
		example_bundle: {
			bundle_kind: string;
			sharing_scope: string;
			proof_boundary: string;
			contains: string[];
		};
	};
}

export default async function PlaygroundPage() {
	const copy = getLocaleMessages().playgroundPage;
	const sample = await loadSampleCorpus();

	return (
		<div className="folo-page-shell folo-unified-shell">
			<div className="folo-page-header">
				<p className="folo-page-kicker">{copy.kicker}</p>
				<h1 className="folo-page-title" data-route-heading tabIndex={-1}>
					{copy.heroTitle}
				</h1>
				<p className="folo-page-subtitle">{copy.heroSubtitle}</p>
			</div>

			<Card className="folo-surface border-border/70">
				<CardHeader>
					<CardTitle>{sample.label}</CardTitle>
					<CardDescription>{sample.description}</CardDescription>
				</CardHeader>
				<CardContent className="space-y-2 text-sm text-muted-foreground">
					<p>{copy.boundaryDescription}</p>
					<div className="flex flex-wrap gap-3">
						<Button asChild variant="hero" size="sm">
							<Link href="/trends">Open compounder front door</Link>
						</Button>
						<Button asChild variant="outline" size="sm">
							<Link href="/watchlists">Open live watchlists</Link>
						</Button>
						<Button asChild variant="outline" size="sm">
							<Link href="/search">{copy.openSearchButton}</Link>
						</Button>
						<Button asChild variant="outline" size="sm">
							<Link href="/proof">{copy.openProofButton}</Link>
						</Button>
						<Button asChild variant="outline" size="sm">
							<Link href="/use-cases/research-pipeline">
								Open research use case
							</Link>
						</Button>
					</div>
				</CardContent>
			</Card>

			<section className="grid gap-4 lg:grid-cols-2">
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<CardTitle>{copy.sampleSourcesTitle}</CardTitle>
					</CardHeader>
					<CardContent className="space-y-3">
						{sample.sources.map((item) => (
							<div
								key={`${item.platform}-${item.title}`}
								className="rounded-lg border border-border/60 bg-muted/20 p-3"
							>
								<p className="font-medium">{item.title}</p>
								<p className="text-sm text-muted-foreground">{item.platform}</p>
								<p className="text-sm text-muted-foreground">{item.url}</p>
							</div>
						))}
					</CardContent>
				</Card>

				<Card className="folo-surface border-border/70">
					<CardHeader>
						<CardTitle>{copy.exampleJobsTitle}</CardTitle>
					</CardHeader>
					<CardContent className="space-y-3">
						{sample.example_jobs.map((item) => (
							<div
								key={item.job_id}
								className="rounded-lg border border-border/60 bg-muted/20 p-3"
							>
								<p className="font-medium">{item.title}</p>
								<p className="text-sm text-muted-foreground">
									{item.platform} · {item.pipeline_final_status}
								</p>
								<p className="text-sm text-muted-foreground">
									{item.digest_excerpt}
								</p>
							</div>
						))}
					</CardContent>
				</Card>
			</section>

			<section className="grid gap-4 lg:grid-cols-2">
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<CardTitle>{copy.retrievalResultsTitle}</CardTitle>
					</CardHeader>
					<CardContent className="space-y-3">
						{sample.example_retrieval_results.map((item, index) => (
							<div
								key={`${item.query}-${index}`}
								className="rounded-lg border border-border/60 bg-muted/20 p-3"
							>
								<p className="font-medium">{item.query}</p>
								<p className="text-sm text-muted-foreground">{item.source}</p>
								<p className="text-sm text-muted-foreground">{item.snippet}</p>
							</div>
						))}
					</CardContent>
				</Card>

				<Card className="folo-surface border-border/70">
					<CardHeader>
						<CardTitle>{copy.exampleWatchlistsTitle}</CardTitle>
					</CardHeader>
					<CardContent className="space-y-3 text-sm text-muted-foreground">
						{sample.example_watchlists.map((item) => (
							<div
								key={`${item.matcher_type}-${item.matcher_value}`}
								className="rounded-lg border border-border/60 bg-muted/20 p-3"
							>
								<p className="font-medium">{item.name}</p>
								<p>
									{item.matcher_type}: <code>{item.matcher_value}</code>
								</p>
							</div>
						))}
						<div className="rounded-lg border border-border/60 bg-muted/20 p-3">
							<p className="font-medium">
								{sample.example_trend.watchlist_name}
							</p>
							<p>
								{copy.recentRunsLabel}:{" "}
								{sample.example_trend.recent_runs.length}
							</p>
						</div>
					</CardContent>
				</Card>
			</section>

			<Card className="folo-surface border-border/70">
				<CardHeader>
					<CardTitle>{copy.exampleBundleTitle}</CardTitle>
					<CardDescription>{copy.exampleBundleDescription}</CardDescription>
				</CardHeader>
				<CardContent className="space-y-2 text-sm text-muted-foreground">
					<p>{sample.example_bundle.bundle_kind}</p>
					<p>
						Sharing scope: <code>{sample.example_bundle.sharing_scope}</code>
					</p>
					<p>{sample.example_bundle.proof_boundary}</p>
					<p>
						This sample bundle explains the product shape. For current local
						evidence, go back to <code>/watchlists</code>, <code>/trends</code>,
						or a real job bundle route.
					</p>
					<ul className="list-disc pl-5">
						{sample.example_bundle.contains.map((item) => (
							<li key={item}>{item}</li>
						))}
					</ul>
				</CardContent>
			</Card>
		</div>
	);
}
