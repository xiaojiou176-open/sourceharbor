"use client";

import Link from "next/link";
import { useState, useTransition } from "react";
import { getFlashMessage, toErrorCode } from "@/app/flash-message";
import { SourceIdentityCard } from "@/components/source-identity-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { apiClient } from "@/lib/api/client";
import type {
	ManualSourceIntakeResponse,
	SubscriptionCategory,
} from "@/lib/api/types";
import { resolveWriteSessionToken } from "@/lib/api/url";
import { editorialMono, editorialSans } from "@/lib/editorial-fonts";
import { resolveManualIntakeIdentity } from "@/lib/source-identity";

const CATEGORY_OPTIONS: Array<{
	value: SubscriptionCategory;
	label: string;
}> = [
	{ value: "misc", label: "Other" },
	{ value: "tech", label: "Tech" },
	{ value: "creator", label: "Creator" },
	{ value: "macro", label: "Macro" },
	{ value: "ops", label: "Operations" },
];

type Copy = {
	title: string;
	description: string;
	placeholder: string;
	hint: string;
	categoryLabel: string;
	tagsLabel: string;
	enabledLabel: string;
	submitButton: string;
	submitPending: string;
	resultsTitle: string;
	resultsDescription: string;
	summaryPrefix: string;
	legend: {
		saveSubscription: string;
		addToToday: string;
		unsupported: string;
	};
	statusLabels: {
		created: string;
		updated: string;
		queued: string;
		reused: string;
		rejected: string;
	};
	emptyState: string;
};

type Props = {
	copy: Copy;
	sessionToken?: string;
};

function statusTone(
	status: string,
): "success" | "warning" | "error" | "secondary" {
	if (status === "created" || status === "updated" || status === "queued") {
		return "success";
	}
	if (status === "reused") {
		return "warning";
	}
	if (status === "rejected") {
		return "error";
	}
	return "secondary";
}

function badgeClass(
	tone: "success" | "warning" | "error" | "secondary",
): string {
	if (tone === "success") {
		return "border-emerald-500/40 bg-emerald-500/10 text-emerald-700";
	}
	if (tone === "warning") {
		return "border-amber-500/40 bg-amber-500/10 text-amber-700";
	}
	if (tone === "error") {
		return "border-destructive/40 bg-destructive/10 text-destructive";
	}
	return "border-border/60 bg-muted/20 text-foreground";
}

function actionLabel(copy: Copy, action: string): string {
	if (action === "save_subscription") {
		return copy.legend.saveSubscription;
	}
	if (action === "add_to_today") {
		return copy.legend.addToToday;
	}
	return copy.legend.unsupported;
}

function statusLabel(copy: Copy, status: string): string {
	if (status === "created") {
		return copy.statusLabels.created;
	}
	if (status === "updated") {
		return copy.statusLabels.updated;
	}
	if (status === "queued") {
		return copy.statusLabels.queued;
	}
	if (status === "reused") {
		return copy.statusLabels.reused;
	}
	return copy.statusLabels.rejected;
}

function buildResultsSummary(result: ManualSourceIntakeResponse): string {
	const parts = [
		result.created_subscriptions
			? `${result.created_subscriptions} saved to your desk`
			: null,
		result.updated_subscriptions
			? `${result.updated_subscriptions} refreshed`
			: null,
		result.queued_manual_items
			? `${result.queued_manual_items} queued for today's reading`
			: null,
		result.reused_manual_items ? `${result.reused_manual_items} reused` : null,
		result.rejected_count ? `${result.rejected_count} rejected` : null,
	].filter(Boolean);

	if (parts.length === 0) {
		return `This pass touched ${result.processed_count} sources.`;
	}

	return `This pass processed ${result.processed_count} sources: ${parts.join(", ")}.`;
}

function buildFeedUniverseHref(
	subscriptionId: string | null | undefined,
): string | null {
	const value = String(subscriptionId || "").trim();
	if (!value) {
		return null;
	}
	return `/feed?sub=${encodeURIComponent(value)}`;
}

export function ManualSourceIntakePanel({ copy, sessionToken }: Props) {
	const effectiveSessionToken = resolveWriteSessionToken(sessionToken);
	const [rawInput, setRawInput] = useState("");
	const [category, setCategory] = useState<SubscriptionCategory>("misc");
	const [tags, setTags] = useState("");
	const [enabled, setEnabled] = useState(true);
	const [result, setResult] = useState<ManualSourceIntakeResponse | null>(null);
	const [errorMessage, setErrorMessage] = useState<string | null>(null);
	const [isPending, startTransition] = useTransition();

	return (
		<Card
			className={`folo-surface border-border/70 ${editorialSans.className}`}
		>
			<CardHeader className="gap-2">
				<p
					className={`text-[11px] uppercase tracking-[0.22em] text-muted-foreground ${editorialMono.className}`}
				>
					Manual front door
				</p>
				<CardTitle className="text-xl font-semibold">{copy.title}</CardTitle>
				<CardDescription>{copy.description}</CardDescription>
			</CardHeader>
			<CardContent className="space-y-4">
				<div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
					<div className="space-y-3">
						<Label htmlFor="manual-source-intake-input">
							URLs / handles / pages
						</Label>
						<Textarea
							id="manual-source-intake-input"
							value={rawInput}
							onChange={(event) => setRawInput(event.target.value)}
							placeholder={copy.placeholder}
							className={`min-h-48 text-sm ${editorialMono.className}`}
						/>
						<p className="text-sm text-muted-foreground">{copy.hint}</p>
					</div>
					<div className="rounded-[1.15rem] border border-border/60 bg-muted/18 p-4">
						<div className="space-y-2 border-b border-border/60 pb-4">
							<Label htmlFor="manual-source-intake-category">
								{copy.categoryLabel}
							</Label>
							<Select
								value={category}
								onValueChange={(value) =>
									setCategory(value as SubscriptionCategory)
								}
							>
								<SelectTrigger
									id="manual-source-intake-category"
									aria-label={copy.categoryLabel}
								>
									<SelectValue placeholder={copy.categoryLabel} />
								</SelectTrigger>
								<SelectContent>
									{CATEGORY_OPTIONS.map((option) => (
										<SelectItem key={option.value} value={option.value}>
											{option.label}
										</SelectItem>
									))}
								</SelectContent>
							</Select>
						</div>
						<div className="space-y-2 border-b border-border/60 py-4">
							<Label htmlFor="manual-source-intake-tags">
								{copy.tagsLabel}
							</Label>
							<input
								id="manual-source-intake-tags"
								value={tags}
								onChange={(event) => setTags(event.target.value)}
								placeholder="ai,weekly,deep-dive"
								className="border-input placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-ring/50 w-full rounded-md border bg-transparent px-3 py-2 text-sm shadow-xs outline-none focus-visible:ring-[3px]"
							/>
						</div>
						<div className="flex items-center gap-3 pt-4">
							<Checkbox
								id="manual-source-intake-enabled"
								checked={enabled}
								onCheckedChange={(checked) => setEnabled(Boolean(checked))}
							/>
							<Label htmlFor="manual-source-intake-enabled">
								{copy.enabledLabel}
							</Label>
						</div>
						<Button
							type="button"
							variant="hero"
							disabled={isPending || rawInput.trim().length === 0}
							onClick={() => {
								setErrorMessage(null);
								startTransition(async () => {
									try {
										const response = await apiClient.submitManualSourceIntake(
											{
												raw_input: rawInput,
												category,
												tags: tags
													.split(",")
													.map((item) => item.trim())
													.filter((item) => item.length > 0),
												enabled,
											},
											{ webSessionToken: effectiveSessionToken },
										);
										setResult(response);
									} catch (error) {
										setErrorMessage(getFlashMessage(toErrorCode(error)));
										setResult(null);
									}
								});
							}}
						>
							{isPending ? copy.submitPending : copy.submitButton}
						</Button>
					</div>
				</div>

				{errorMessage ? (
					<p
						className="alert alert-enter error"
						role="alert"
						aria-live="assertive"
					>
						{errorMessage}
					</p>
				) : null}

				{result ? (
					<div className="space-y-4 rounded-[1.4rem] border border-border/60 bg-muted/15 p-4">
						<div className="space-y-1">
							<p
								className={`text-[11px] uppercase tracking-[0.22em] text-muted-foreground ${editorialMono.className}`}
							>
								Outcome receipt
							</p>
							<p className="font-medium">{copy.resultsTitle}</p>
							<p className="text-sm text-muted-foreground">
								{buildResultsSummary(result)}
							</p>
							<p className="text-sm text-muted-foreground">
								{copy.resultsDescription}
							</p>
						</div>
						<div className="grid gap-3 lg:grid-cols-2">
							{result.results.map((item) => {
								const tone = statusTone(item.status);
								const identity = resolveManualIntakeIdentity(item);
								const feedUniverseHref = buildFeedUniverseHref(
									item.matched_subscription_id || item.subscription_id,
								);
								const jobHref = item.job_id
									? `/jobs?job_id=${encodeURIComponent(item.job_id)}`
									: null;
								const readerHref = item.reader_route
									?.trim()
									.startsWith("/reader/")
									? item.reader_route.trim()
									: null;
								return (
									<div
										key={`${item.line_number}-${item.raw_input}`}
										className="space-y-2 rounded-[1.2rem] border border-border/60 bg-background/70 p-3"
									>
										<div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
											<Badge
												variant="outline"
												className={badgeClass("secondary")}
											>
												Line {item.line_number}
											</Badge>
											<Badge variant="outline" className={badgeClass(tone)}>
												{statusLabel(copy, item.status)}
											</Badge>
											<Badge
												variant="outline"
												className={badgeClass("secondary")}
											>
												{actionLabel(
													copy,
													item.applied_action ?? item.recommended_action,
												)}
											</Badge>
										</div>
										<SourceIdentityCard
											identity={{
												...identity,
												description:
													identity.description ||
													[item.platform, item.source_type, item.rsshub_route]
														.filter(Boolean)
														.join(" · ") ||
													copy.emptyState,
											}}
											compact
											action={
												<div className="flex flex-wrap gap-3 text-sm">
													{readerHref ? (
														<Link
															href={readerHref}
															className="underline underline-offset-4"
														>
															Read this edition
														</Link>
													) : null}
													{feedUniverseHref ? (
														<Link
															href={feedUniverseHref}
															className="underline underline-offset-4"
														>
															Open source desk
														</Link>
													) : null}
													{jobHref ? (
														<Link
															href={jobHref}
															className="underline underline-offset-4"
														>
															Inspect job trace
														</Link>
													) : null}
												</div>
											}
										/>
										<div className="rounded-xl border border-border/50 bg-muted/20 px-3 py-2 text-xs text-muted-foreground">
											<p className={`break-all ${editorialMono.className}`}>
												{item.raw_input}
											</p>
											{item.published_document_title ? (
												<p className="mt-2">
													Reader edition ready · {item.published_document_title}
													{item.published_document_publish_status
														? ` · ${item.published_document_publish_status}`
														: ""}
												</p>
											) : null}
											<p className="mt-2">{item.message}</p>
										</div>
									</div>
								);
							})}
						</div>
					</div>
				) : null}
			</CardContent>
		</Card>
	);
}
