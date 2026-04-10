"use client";

import { useState, useTransition } from "react";
import { getFlashMessage, toErrorCode } from "@/app/flash-message";
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

export function ManualSourceIntakePanel({ copy, sessionToken }: Props) {
	const [rawInput, setRawInput] = useState("");
	const [category, setCategory] = useState<SubscriptionCategory>("misc");
	const [tags, setTags] = useState("");
	const [enabled, setEnabled] = useState(true);
	const [result, setResult] = useState<ManualSourceIntakeResponse | null>(null);
	const [errorMessage, setErrorMessage] = useState<string | null>(null);
	const [isPending, startTransition] = useTransition();

	return (
		<Card className="folo-surface border-border/70">
			<CardHeader className="gap-2">
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
							className="min-h-48 font-mono text-sm"
						/>
						<p className="text-sm text-muted-foreground">{copy.hint}</p>
					</div>
					<div className="space-y-4 rounded-xl border border-border/60 bg-muted/20 p-4">
						<div className="space-y-2">
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
						<div className="space-y-2">
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
						<div className="flex items-center gap-3">
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
											{ webSessionToken: sessionToken ?? null },
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
					<div className="space-y-3 rounded-xl border border-border/60 bg-muted/15 p-4">
						<div className="space-y-1">
							<p className="font-medium">{copy.resultsTitle}</p>
							<p className="text-sm text-muted-foreground">
								{copy.summaryPrefix} {result.processed_count} · subscriptions +
								{result.created_subscriptions}/~{result.updated_subscriptions} ·
								today +{result.queued_manual_items}/=
								{result.reused_manual_items} · rejected {result.rejected_count}
							</p>
							<p className="text-sm text-muted-foreground">
								{copy.resultsDescription}
							</p>
						</div>
						<div className="overflow-x-auto rounded-lg border">
							<table className="min-w-[960px] w-full text-sm">
								<thead className="bg-muted/40">
									<tr className="[&_th]:px-3 [&_th]:py-2.5 [&_th]:text-left [&_th]:text-xs [&_th]:font-medium [&_th]:text-muted-foreground">
										<th scope="col">Line</th>
										<th scope="col">Input</th>
										<th scope="col">Resolution</th>
										<th scope="col">Action</th>
										<th scope="col">Status</th>
										<th scope="col">Message</th>
									</tr>
								</thead>
								<tbody>
									{result.results.map((item) => {
										const tone = statusTone(item.status);
										return (
											<tr
												key={`${item.line_number}-${item.raw_input}`}
												className="border-b align-top"
											>
												<td className="px-3 py-3 text-xs text-muted-foreground">
													{item.line_number}
												</td>
												<td className="px-3 py-3 font-mono text-xs">
													{item.raw_input}
												</td>
												<td className="px-3 py-3">
													<div className="font-medium">
														{item.display_name ||
															item.source_value ||
															item.source_url ||
															copy.emptyState}
													</div>
													<div className="text-xs text-muted-foreground">
														{[
															item.platform,
															item.source_type,
															item.rsshub_route,
														]
															.filter(Boolean)
															.join(" · ") || copy.emptyState}
													</div>
												</td>
												<td className="px-3 py-3">
													<Badge
														variant="outline"
														className={badgeClass("secondary")}
													>
														{actionLabel(
															copy,
															item.applied_action ?? item.recommended_action,
														)}
													</Badge>
												</td>
												<td className="px-3 py-3">
													<Badge variant="outline" className={badgeClass(tone)}>
														{statusLabel(copy, item.status)}
													</Badge>
												</td>
												<td className="px-3 py-3 text-muted-foreground">
													{item.message}
												</td>
											</tr>
										);
									})}
								</tbody>
							</table>
						</div>
					</div>
				) : null}
			</CardContent>
		</Card>
	);
}
