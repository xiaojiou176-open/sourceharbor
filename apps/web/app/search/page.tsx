import type { Metadata } from "next";
import Link from "next/link";

import { FormInputField, FormSelectField } from "@/components/form-field";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
} from "@/components/ui/card";
import { apiClient } from "@/lib/api/client";
import type { RetrievalSearchMode } from "@/lib/api/types";
import { getLocaleMessages } from "@/lib/i18n/messages";
import {
	resolveSearchParams,
	type SearchParamsInput,
} from "@/lib/search-params";
import { buildProductMetadata } from "@/lib/seo";

const searchCopy = getLocaleMessages().searchPage;
const briefingsCopy = getLocaleMessages().briefingsPage;

export const metadata: Metadata = buildProductMetadata({
	title: searchCopy.metadataTitle,
	description: searchCopy.metadataDescription,
	route: "search",
});

type SearchPageProps = {
	searchParams?: SearchParamsInput;
};

function humanizeSource(source: string): string {
	return source
		.split(/[_-]+/)
		.filter(Boolean)
		.map((part) => part.charAt(0).toUpperCase() + part.slice(1))
		.join(" ");
}

export default async function SearchPage({ searchParams }: SearchPageProps) {
	const copy = getLocaleMessages().searchPage;
	const modeOptions = [
		{ value: "keyword", label: copy.modeOptions.keyword },
		{ value: "semantic", label: copy.modeOptions.semantic },
		{ value: "hybrid", label: copy.modeOptions.hybrid },
	];
	const { q, query, mode, top_k, intent, platform } = await resolveSearchParams(
		searchParams,
		["q", "query", "mode", "top_k", "intent", "platform"] as const,
	);
	const queryValue = query.trim() || q.trim();
	const trimmedMode = mode.trim();
	const normalizedMode: RetrievalSearchMode =
		trimmedMode === "semantic" || trimmedMode === "hybrid"
			? trimmedMode
			: "keyword";
	const parsedTopK = Number.parseInt(top_k, 10);
	const safeTopK =
		Number.isFinite(parsedTopK) && parsedTopK > 0
			? Math.min(parsedTopK, 20)
			: 8;
	const askIntent = intent.trim() === "ask";
	const safePlatform = platform.trim().toLowerCase();
	const basePlatformOptions = [
		{ value: "", label: copy.platformOptions.all },
		{ value: "youtube", label: copy.platformOptions.youtube },
		{ value: "bilibili", label: copy.platformOptions.bilibili },
		{ value: "rss", label: copy.platformOptions.rss },
	];
	const platformOptions = safePlatform
		? basePlatformOptions.some((option) => option.value === safePlatform)
			? basePlatformOptions
			: [
					...basePlatformOptions,
					{ value: safePlatform, label: humanizeSource(safePlatform) },
				]
		: basePlatformOptions;

	let payload: Awaited<ReturnType<typeof apiClient.searchRetrieval>> | null =
		null;
	let error = false;
	if (queryValue) {
		try {
			payload = await apiClient.searchRetrieval({
				query: queryValue,
				mode: normalizedMode,
				top_k: safeTopK,
				filters: safePlatform ? { platform: safePlatform } : {},
			});
		} catch {
			error = true;
		}
	}

	const results = payload?.items ?? [];

	return (
		<div className="folo-page-shell folo-unified-shell">
			<div className="folo-page-header">
				<p className="folo-page-kicker">
					{askIntent ? copy.askKicker : copy.searchKicker}
				</p>
				<h1 className="folo-page-title" data-route-heading tabIndex={-1}>
					{askIntent ? copy.askTitle : copy.searchTitle}
				</h1>
				<p className="folo-page-subtitle">
					{askIntent ? copy.askSubtitle : copy.searchSubtitle}
				</p>
			</div>

			<Card className="folo-surface border-border/70">
				<CardHeader>
					<h2 className="text-xl font-semibold">
						{askIntent ? copy.askFormTitle : copy.searchFormTitle}
					</h2>
					<CardDescription>
						{askIntent ? copy.askFormDescription : copy.searchFormDescription}
					</CardDescription>
				</CardHeader>
				<CardContent>
					<form
						method="GET"
						className="grid gap-4 lg:grid-cols-[1.7fr_0.8fr_0.5fr_auto]"
					>
						<input type="hidden" name="intent" value={askIntent ? "ask" : ""} />
						<FormInputField
							name="q"
							label={askIntent ? copy.questionLabel : copy.queryLabel}
							placeholder={
								askIntent ? copy.questionPlaceholder : copy.queryPlaceholder
							}
							defaultValue={queryValue}
							hint={askIntent ? copy.askHint : copy.searchHint}
						/>
						<FormSelectField
							name="mode"
							label={askIntent ? copy.groundingModeLabel : copy.modeLabel}
							defaultValue={normalizedMode}
							options={modeOptions}
						/>
						<FormSelectField
							name="platform"
							label={copy.platformLabel}
							defaultValue={safePlatform}
							options={platformOptions}
						/>
						<FormInputField
							name="top_k"
							label={copy.topKLabel}
							type="number"
							min={1}
							max={20}
							defaultValue={safeTopK}
						/>
						<div className="flex items-end gap-3">
							<Button type="submit" variant="hero" size="sm">
								{askIntent ? copy.askButton : copy.searchButton}
							</Button>
							<Button asChild variant="ghost" size="sm">
								<Link href={askIntent ? "/ask" : "/search"}>
									{copy.clearButton}
								</Link>
							</Button>
						</div>
					</form>
				</CardContent>
			</Card>

			<section className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<h2 className="text-xl font-semibold">
							{askIntent ? copy.askTruthTitle : copy.searchTruthTitle}
						</h2>
					</CardHeader>
					<CardContent className="space-y-3 text-sm text-muted-foreground">
						<p>{askIntent ? copy.askTruthPrimary : copy.searchTruthPrimary}</p>
						<p>
							{askIntent ? copy.askTruthSecondary : copy.searchTruthSecondary}
						</p>
						{askIntent ? <p>{copy.askTruthNote}</p> : null}
						<Button asChild variant="outline" size="sm">
							<Link href={askIntent ? "/ask" : "/ask"}>
								{askIntent ? copy.askTruthCta : copy.searchTruthCta}
							</Link>
						</Button>
						<Button asChild variant="outline" size="sm">
							<Link href="/briefings">{briefingsCopy.openBriefingButton}</Link>
						</Button>
					</CardContent>
				</Card>
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<h2 className="text-xl font-semibold">
							{askIntent ? copy.askContractTitle : copy.searchContractTitle}
						</h2>
					</CardHeader>
					<CardContent className="space-y-3 text-sm text-muted-foreground">
						<p>
							{askIntent ? copy.askContractPrimary : copy.searchContractPrimary}
						</p>
						<p>
							{askIntent
								? copy.askContractSecondary
								: copy.searchContractSecondary}
						</p>
					</CardContent>
				</Card>
			</section>

			<Card className="folo-surface border-border/70">
				<CardHeader>
					<h2 className="text-xl font-semibold">
						{askIntent ? copy.askResultsTitle : copy.searchResultsTitle}
					</h2>
					<CardDescription>
						{queryValue
							? `${askIntent ? copy.askResultsPrefix : copy.searchResultsPrefix} for “${queryValue}”.`
							: askIntent
								? copy.askRunPrompt
								: copy.searchRunPrompt}
					</CardDescription>
				</CardHeader>
				<CardContent className="space-y-4">
					{error ? (
						<p className="text-sm text-muted-foreground">
							{copy.requestFailed}
						</p>
					) : null}
					{!error && queryValue && results.length === 0 ? (
						<p className="text-sm text-muted-foreground">{copy.noResults}</p>
					) : null}
					{results.map((item, index) => (
						<Card
							key={`${item.job_id}-${item.source}-${index}`}
							className="border-border/60"
						>
							<CardContent className="space-y-4 pt-6">
								<div className="flex flex-wrap gap-2">
									<Badge variant="outline">{humanizeSource(item.source)}</Badge>
									<Badge variant="outline">{item.platform || "unknown"}</Badge>
									<Badge variant="outline">score {item.score.toFixed(2)}</Badge>
									{normalizedMode !== "keyword" ? (
										<Badge variant="secondary">{copy.experimentalMode}</Badge>
									) : null}
								</div>
								<div className="space-y-2">
									<h3 className="text-lg font-semibold">
										{item.title?.trim() || `Job ${item.job_id}`}
									</h3>
									<p className="text-sm text-muted-foreground">
										{item.snippet}
									</p>
								</div>
								<div className="flex flex-wrap gap-3">
									<Button asChild variant="outline" size="sm">
										<Link
											href={`/jobs?job_id=${encodeURIComponent(item.job_id)}`}
										>
											{copy.openJobTraceButton}
										</Link>
									</Button>
									<Button asChild variant="outline" size="sm">
										<Link
											href={`/knowledge?job_id=${encodeURIComponent(item.job_id)}`}
										>
											{copy.openKnowledgeCardsButton}
										</Link>
									</Button>
									<Button asChild variant="outline" size="sm">
										<Link
											href={`/feed?item=${encodeURIComponent(item.job_id)}`}
										>
											{copy.openFeedEntryButton}
										</Link>
									</Button>
									{item.source_url ? (
										<Button asChild variant="ghost" size="sm">
											<a
												href={item.source_url}
												target="_blank"
												rel="noreferrer"
											>
												{copy.openSourceButton}
											</a>
										</Button>
									) : null}
								</div>
							</CardContent>
						</Card>
					))}
				</CardContent>
			</Card>
		</div>
	);
}
