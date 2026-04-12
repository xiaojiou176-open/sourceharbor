import type { Metadata } from "next";
import Link from "next/link";

import { FormInputField, FormSelectField } from "@/components/form-field";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
} from "@/components/ui/card";
import { apiClient } from "@/lib/api/client";
import { getLocaleMessages } from "@/lib/i18n/messages";
import {
	resolveSearchParams,
	type SearchParamsInput,
} from "@/lib/search-params";
import { buildProductMetadata } from "@/lib/seo";

const knowledgeCopy = getLocaleMessages().knowledgePage;

export const metadata: Metadata = buildProductMetadata({
	title: knowledgeCopy.metadataTitle,
	description: knowledgeCopy.metadataDescription,
	route: "knowledge",
});

type KnowledgePageProps = {
	searchParams?: SearchParamsInput;
};

function humanizeToken(value: string): string {
	return value
		.split(/[_-]+/)
		.filter(Boolean)
		.map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
		.join(" ");
}

function compactId(value: string | undefined): string | null {
	const normalized = value?.trim() ?? "";
	if (!normalized) {
		return null;
	}
	if (normalized.length <= 16) {
		return normalized;
	}
	return `${normalized.slice(0, 8)}…${normalized.slice(-6)}`;
}

function toMetadataTokens(
	metadata: Record<string, unknown> | undefined,
): string[] {
	if (!metadata) {
		return [];
	}

	const tokens: string[] = [];
	for (const [key, rawValue] of Object.entries(metadata)) {
		if (
			typeof rawValue === "string" ||
			typeof rawValue === "number" ||
			typeof rawValue === "boolean"
		) {
			tokens.push(`${humanizeToken(key)}: ${String(rawValue)}`);
		}
	}
	return tokens.slice(0, 4);
}

export default async function KnowledgePage({
	searchParams,
}: KnowledgePageProps) {
	const copy = getLocaleMessages().knowledgePage;
	const {
		job_id: jobId,
		video_id: videoId,
		card_type: cardType,
		topic_key: topicKey,
		claim_kind: claimKind,
		limit,
	} = await resolveSearchParams(searchParams, [
		"job_id",
		"video_id",
		"card_type",
		"topic_key",
		"claim_kind",
		"limit",
	] as const);
	const safeJobId = jobId.trim();
	const safeVideoId = videoId.trim();
	const safeCardType = cardType.trim();
	const safeTopicKey = topicKey.trim();
	const safeClaimKind = claimKind.trim();
	const parsedLimit = Number.parseInt(limit, 10);
	const safeLimit =
		Number.isFinite(parsedLimit) && parsedLimit > 0
			? Math.min(parsedLimit, 200)
			: 50;

	let cards: Awaited<ReturnType<typeof apiClient.listKnowledgeCards>> = [];
	let error = false;
	try {
		cards = await apiClient.listKnowledgeCards({
			job_id: safeJobId || undefined,
			video_id: safeVideoId || undefined,
			card_type: safeCardType || undefined,
			topic_key: safeTopicKey || undefined,
			claim_kind: safeClaimKind || undefined,
			limit: safeLimit,
		});
	} catch {
		error = true;
	}

	const totalCards = cards.length;
	const uniqueJobs = new Set(cards.map((card) => card.job_id).filter(Boolean))
		.size;
	const uniqueCardTypes = new Set(cards.map((card) => card.card_type)).size;
	const cardTypeCounts = Array.from(
		cards.reduce((map, card) => {
			map.set(card.card_type, (map.get(card.card_type) ?? 0) + 1);
			return map;
		}, new Map<string, number>()),
	).sort(([left], [right]) => left.localeCompare(right));
	const cardTypeOptions = [
		{ value: "", label: "All card types" },
		...Array.from(
			new Set(
				[
					...cards.map((card) => card.card_type),
					...(safeCardType ? [safeCardType] : []),
				].filter(Boolean),
			),
		)
			.sort((left, right) => left.localeCompare(right))
			.map((value) => ({
				value,
				label: humanizeToken(value),
			})),
	];
	const topicOptions = [
		{ value: "", label: "All topics" },
		...Array.from(
			new Set(
				cards
					.map((card) => String(card.metadata_json?.topic_key ?? "").trim())
					.filter(Boolean)
					.concat(safeTopicKey ? [safeTopicKey] : []),
			),
		)
			.sort((left, right) => left.localeCompare(right))
			.map((value) => ({
				value,
				label:
					String(
						cards.find((card) => card.metadata_json?.topic_key === value)
							?.metadata_json?.topic_label ?? humanizeToken(value),
					) || humanizeToken(value),
			})),
	];
	const claimKindOptions = [
		{ value: "", label: "All claim kinds" },
		...Array.from(
			new Set(
				cards
					.map((card) => String(card.metadata_json?.claim_kind ?? "").trim())
					.filter(Boolean)
					.concat(safeClaimKind ? [safeClaimKind] : []),
			),
		)
			.sort((left, right) => left.localeCompare(right))
			.map((value) => ({
				value,
				label: humanizeToken(value),
			})),
	];

	const buildKnowledgeHref = ({
		jobIdValue,
		videoIdValue,
		cardTypeValue,
		topicKeyValue,
		claimKindValue,
	}: {
		jobIdValue?: string;
		videoIdValue?: string;
		cardTypeValue?: string;
		topicKeyValue?: string;
		claimKindValue?: string;
	}) => {
		const params = new URLSearchParams();
		if (jobIdValue) {
			params.set("job_id", jobIdValue);
		}
		if (videoIdValue) {
			params.set("video_id", videoIdValue);
		}
		if (cardTypeValue) {
			params.set("card_type", cardTypeValue);
		}
		if (topicKeyValue) {
			params.set("topic_key", topicKeyValue);
		}
		if (claimKindValue) {
			params.set("claim_kind", claimKindValue);
		}
		if (safeLimit !== 50) {
			params.set("limit", String(safeLimit));
		}
		const query = params.toString();
		return `/knowledge${query ? `?${query}` : ""}`;
	};

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
					<h2 className="text-xl font-semibold">{copy.filterTitle}</h2>
					<CardDescription>{copy.filterDescription}</CardDescription>
				</CardHeader>
				<CardContent>
					<form method="GET" className="grid gap-4 lg:grid-cols-2">
						<FormInputField
							id="knowledge-job-id"
							name="job_id"
							label={copy.filterLabels.jobId}
							type="text"
							placeholder={copy.idPlaceholder}
							defaultValue={safeJobId}
							data-field-kind="identifier"
						/>
						<FormInputField
							id="knowledge-video-id"
							name="video_id"
							label={copy.filterLabels.videoId}
							type="text"
							placeholder={copy.idPlaceholder}
							defaultValue={safeVideoId}
							data-field-kind="identifier"
						/>
						<FormSelectField
							name="card_type"
							label={copy.filterLabels.cardType}
							defaultValue={safeCardType}
							options={cardTypeOptions}
						/>
						<FormSelectField
							name="topic_key"
							label={copy.filterLabels.topic}
							defaultValue={safeTopicKey}
							options={topicOptions}
						/>
						<FormSelectField
							name="claim_kind"
							label={copy.filterLabels.claimKind}
							defaultValue={safeClaimKind}
							options={claimKindOptions}
						/>
						<FormInputField
							id="knowledge-limit"
							name="limit"
							label={copy.filterLabels.limit}
							type="number"
							min={1}
							max={200}
							defaultValue={safeLimit}
						/>
						<div className="flex flex-wrap items-center gap-3 lg:col-span-2">
							<Button type="submit" variant="hero" size="sm">
								{copy.filterButton}
							</Button>
							<Button asChild variant="ghost" size="sm">
								<Link href="/knowledge">{copy.clearButton}</Link>
							</Button>
						</div>
					</form>
				</CardContent>
			</Card>

			{!error ? (
				<section className="grid gap-4 md:grid-cols-3">
					<Card className="folo-surface border-border/70">
						<CardHeader>
							<p className="text-sm text-muted-foreground">{copy.totalCards}</p>
							<p className="text-3xl font-semibold">{totalCards}</p>
						</CardHeader>
					</Card>
					<Card className="folo-surface border-border/70">
						<CardHeader>
							<p className="text-sm text-muted-foreground">{copy.uniqueJobs}</p>
							<p className="text-3xl font-semibold">{uniqueJobs}</p>
						</CardHeader>
					</Card>
					<Card className="folo-surface border-border/70">
						<CardHeader>
							<p className="text-sm text-muted-foreground">{copy.cardTypes}</p>
							<p className="text-3xl font-semibold">{uniqueCardTypes}</p>
						</CardHeader>
					</Card>
				</section>
			) : null}

			<Card className="folo-surface border-border/70">
				<CardHeader>
					<h2 className="text-xl font-semibold">{copy.sectionTitle}</h2>
					<CardDescription>
						{copy.sectionDescription}{" "}
						<Link href="/jobs">{copy.jobTraceCta}</Link>.
					</CardDescription>
				</CardHeader>
				<CardContent className="space-y-4">
					{error ? (
						<p className="text-sm text-muted-foreground">{copy.loadError}</p>
					) : cards.length === 0 ? (
						<p className="text-sm text-muted-foreground">{copy.empty}</p>
					) : (
						<>
							<div className="flex flex-wrap gap-2">
								{cardTypeCounts.map(([type, count]) => (
									<Button key={type} asChild variant="outline" size="xs">
										<Link
											href={buildKnowledgeHref({
												jobIdValue: safeJobId || undefined,
												videoIdValue: safeVideoId || undefined,
												cardTypeValue: type,
												topicKeyValue: safeTopicKey || undefined,
												claimKindValue: safeClaimKind || undefined,
											})}
										>
											{humanizeToken(type)} ({count})
										</Link>
									</Button>
								))}
							</div>
							<ul className="space-y-3 text-sm">
								{cards.map((card, index) => (
									<li
										key={
											card.id ??
											`${card.card_type}-${card.order_index}-${index}`
										}
										className="rounded-lg border border-border/60 bg-muted/20 p-3"
									>
										<div className="flex flex-wrap items-start justify-between gap-3">
											<div className="space-y-1">
												<p className="text-xs uppercase tracking-wide text-muted-foreground">
													{humanizeToken(card.card_type)} ·{" "}
													{humanizeToken(card.source_section)}
												</p>
												<p className="font-medium">
													{card.title ??
														`${humanizeToken(card.card_type)} #${card.order_index + 1}`}
												</p>
											</div>
											<div className="flex flex-wrap gap-2">
												{card.job_id ? (
													<Button asChild variant="ghost" size="xs">
														<Link
															href={`/jobs?job_id=${encodeURIComponent(card.job_id)}`}
															aria-label={`${copy.openJobTraceAriaPrefix} ${card.job_id}`}
														>
															{copy.openJobTraceButton}
														</Link>
													</Button>
												) : null}
												<Button asChild variant="ghost" size="xs">
													<Link
														href={buildKnowledgeHref({
															jobIdValue: safeJobId || undefined,
															videoIdValue: safeVideoId || undefined,
															cardTypeValue: card.card_type,
															topicKeyValue:
																String(
																	card.metadata_json?.topic_key ?? "",
																).trim() ||
																safeTopicKey ||
																undefined,
															claimKindValue:
																String(
																	card.metadata_json?.claim_kind ?? "",
																).trim() ||
																safeClaimKind ||
																undefined,
														})}
													>
														{copy.sameTypeButton}
													</Link>
												</Button>
											</div>
										</div>
										<p className="mt-2 text-muted-foreground">{card.body}</p>
										<div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
											{compactId(card.job_id) ? (
												<span>
													{copy.metaLabels.job}: {compactId(card.job_id)}
												</span>
											) : null}
											{compactId(card.video_id) ? (
												<span>
													{copy.metaLabels.video}: {compactId(card.video_id)}
												</span>
											) : null}
											<span>
												{copy.metaLabels.order}: {card.order_index + 1}
											</span>
											{card.metadata_json?.topic_label ? (
												<span>
													{copy.metaLabels.topic}:{" "}
													{String(card.metadata_json.topic_label)}
												</span>
											) : null}
										</div>
										{toMetadataTokens(card.metadata_json).length > 0 ? (
											<div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
												{toMetadataTokens(card.metadata_json).map((token) => (
													<span
														key={token}
														className="rounded-full border border-border/60 px-2 py-1"
													>
														{token}
													</span>
												))}
											</div>
										) : null}
									</li>
								))}
							</ul>
						</>
					)}
				</CardContent>
			</Card>
		</div>
	);
}
