"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { getFlashMessage, toErrorCode } from "@/app/flash-message";
import { SourceIdentityCard } from "@/components/source-identity-card";
import { StatusBadge } from "@/components/status-badge";
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
import { apiClient } from "@/lib/api/client";
import type { Subscription, SubscriptionCategory } from "@/lib/api/types";
import { editorialMono, editorialSans } from "@/lib/editorial-fonts";
import { formatDateTime } from "@/lib/format";
import { resolveSubscriptionIdentity } from "@/lib/source-identity";
import { cn } from "@/lib/utils";

const CATEGORIES: SubscriptionCategory[] = [
	"tech",
	"creator",
	"macro",
	"ops",
	"misc",
];
const UNDO_WINDOW_MS = 10_000;
const CATEGORY_LABELS: Record<SubscriptionCategory, string> = {
	tech: "Tech",
	creator: "Creator",
	macro: "Macro",
	ops: "Operations",
	misc: "Other",
};

type Props = {
	subscriptions: Subscription[];
	sessionToken?: string;
};

type UndoContext = {
	ids: string[];
	previousCategories: Record<string, SubscriptionCategory>;
	nextCategory: SubscriptionCategory;
	expiresAt: number;
};

type UndoHistory = {
	message: string;
	isError: boolean;
};

function humanizeSourceType(value: string): string {
	if (value === "youtube_channel_id") {
		return "YouTube channel ID";
	}
	if (value === "youtube_user") {
		return "YouTube handle";
	}
	if (value === "bilibili_uid") {
		return "Bilibili UID";
	}
	if (value === "rsshub_route") {
		return "RSSHub route";
	}
	if (value === "url") {
		return "Source URL";
	}
	return value;
}

export function SubscriptionBatchPanel({ subscriptions, sessionToken }: Props) {
	const router = useRouter();
	const [visibleSubscriptions, setVisibleSubscriptions] =
		useState<Subscription[]>(subscriptions);
	const [selected, setSelected] = useState<Set<string>>(new Set());
	const [batchCategory, setBatchCategory] =
		useState<SubscriptionCategory>("misc");
	const [applying, setApplying] = useState(false);
	const [undoing, setUndoing] = useState(false);
	const [applyResult, setApplyResult] = useState<string | null>(null);
	const [undoContext, setUndoContext] = useState<UndoContext | null>(null);
	const [undoRemainingSeconds, setUndoRemainingSeconds] = useState(0);
	const [undoHistory, setUndoHistory] = useState<UndoHistory | null>(null);
	const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
	const [deletingId, setDeletingId] = useState<string | null>(null);
	const [deleteStatusMessage, setDeleteStatusMessage] = useState("");
	const confirmDeleteRefs = useRef<Record<string, HTMLButtonElement | null>>(
		{},
	);
	const deleteTriggerRefs = useRef<Record<string, HTMLButtonElement | null>>(
		{},
	);
	const restoreDeleteTriggerFocusIdRef = useRef<string | null>(null);
	const undoTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
	const undoCountdownRef = useRef<ReturnType<typeof setInterval> | null>(null);

	const clearUndoTimer = useCallback(() => {
		if (!undoTimerRef.current) {
			if (undoCountdownRef.current) {
				clearInterval(undoCountdownRef.current);
				undoCountdownRef.current = null;
			}
			return;
		}
		clearTimeout(undoTimerRef.current);
		undoTimerRef.current = null;
		if (undoCountdownRef.current) {
			clearInterval(undoCountdownRef.current);
			undoCountdownRef.current = null;
		}
	}, []);

	function clearUndoContext() {
		clearUndoTimer();
		setUndoContext(null);
		setUndoRemainingSeconds(0);
	}

	useEffect(() => {
		setVisibleSubscriptions(subscriptions);
	}, [subscriptions]);

	useEffect(() => {
		if (!pendingDeleteId) {
			return;
		}
		confirmDeleteRefs.current[pendingDeleteId]?.focus();
	}, [pendingDeleteId]);

	useEffect(() => {
		if (
			pendingDeleteId ||
			deletingId ||
			!restoreDeleteTriggerFocusIdRef.current
		) {
			return;
		}
		const targetId = restoreDeleteTriggerFocusIdRef.current;
		restoreDeleteTriggerFocusIdRef.current = null;
		deleteTriggerRefs.current[targetId]?.focus();
	}, [pendingDeleteId, deletingId]);

	useEffect(() => {
		return () => {
			clearUndoTimer();
		};
	}, [clearUndoTimer]);

	useEffect(() => {
		if (!undoContext) {
			return;
		}
		const updateRemaining = () => {
			const remainingMs = undoContext.expiresAt - Date.now();
			setUndoRemainingSeconds(Math.max(0, Math.ceil(remainingMs / 1000)));
		};
		updateRemaining();
		undoCountdownRef.current = setInterval(updateRemaining, 1000);
		undoTimerRef.current = setTimeout(
			() => {
				setUndoContext(null);
				setUndoRemainingSeconds(0);
				setUndoHistory({
					message: "The bulk category undo window expired.",
					isError: false,
				});
				if (undoCountdownRef.current) {
					clearInterval(undoCountdownRef.current);
					undoCountdownRef.current = null;
				}
				undoTimerRef.current = null;
			},
			Math.max(0, undoContext.expiresAt - Date.now()),
		);
		return () => {
			clearUndoTimer();
		};
	}, [undoContext, clearUndoTimer]);

	function toggleAll() {
		if (selected.size === visibleSubscriptions.length) {
			setSelected(new Set());
		} else {
			setSelected(new Set(visibleSubscriptions.map((s) => s.id)));
		}
	}

	function toggleOne(id: string) {
		setSelected((prev) => {
			const next = new Set(prev);
			if (next.has(id)) {
				next.delete(id);
			} else {
				next.add(id);
			}
			return next;
		});
	}

	function getCategoryLabel(category: SubscriptionCategory): string {
		return CATEGORY_LABELS[category];
	}

	function writeOptions() {
		return sessionToken ? { webSessionToken: sessionToken } : undefined;
	}

	// In cross-origin local E2E mode, preflight may reject custom session headers.
	function shouldRetryWithoutSessionHeader(err: unknown): boolean {
		return err instanceof Error && err.message === "ERR_REQUEST_FAILED";
	}

	async function deleteSubscriptionWithAuth(id: string) {
		const options = writeOptions();
		if (!options) {
			return apiClient.deleteSubscription(id);
		}
		try {
			return await apiClient.deleteSubscription(id, options);
		} catch (err) {
			if (shouldRetryWithoutSessionHeader(err)) {
				return apiClient.deleteSubscription(id);
			}
			throw err;
		}
	}

	async function batchUpdateWithAuth(payload: {
		ids: string[];
		category: SubscriptionCategory;
	}) {
		const options = writeOptions();
		if (!options) {
			return apiClient.batchUpdateSubscriptionCategory(payload);
		}
		try {
			return await apiClient.batchUpdateSubscriptionCategory(payload, options);
		} catch (err) {
			if (shouldRetryWithoutSessionHeader(err)) {
				return apiClient.batchUpdateSubscriptionCategory(payload);
			}
			throw err;
		}
	}

	async function handleDeleteConfirm(id: string) {
		const targetName = getSubscriptionDisplayNameById(id);
		setDeletingId(id);
		setPendingDeleteId(null);
		setDeleteStatusMessage(`Deleting "${targetName}".`);
		try {
			await deleteSubscriptionWithAuth(id);
			setVisibleSubscriptions((prev) => prev.filter((item) => item.id !== id));
			setSelected((prev) => {
				const next = new Set(prev);
				next.delete(id);
				return next;
			});
			setApplyResult(null);
			setDeleteStatusMessage(`Deleted "${targetName}".`);
			router.replace("/subscriptions?status=success&code=SUBSCRIPTION_DELETED");
			router.refresh();
		} catch (err) {
			const message = `Delete failed: ${getFlashMessage(toErrorCode(err))}`;
			setApplyResult(message);
			setDeleteStatusMessage(
				`Deleting "${targetName}" failed. Please try again.`,
			);
			restoreDeleteTriggerFocusIdRef.current = id;
		} finally {
			setDeletingId(null);
		}
	}

	async function handleApplyCategory() {
		if (selected.size === 0) {
			return;
		}
		const selectedIds = Array.from(selected);
		const previousCategories: Record<string, SubscriptionCategory> = {};
		visibleSubscriptions.forEach((item) => {
			if (selected.has(item.id)) {
				previousCategories[item.id] = item.category;
			}
		});
		clearUndoContext();
		setApplying(true);
		setApplyResult(null);
		try {
			const result = await batchUpdateWithAuth({
				ids: selectedIds,
				category: batchCategory,
			});
			setVisibleSubscriptions((prev) =>
				prev.map((item) =>
					selectedIds.includes(item.id)
						? { ...item, category: batchCategory }
						: item,
				),
			);
			setUndoContext({
				ids: selectedIds,
				previousCategories,
				nextCategory: batchCategory,
				expiresAt: Date.now() + UNDO_WINDOW_MS,
			});
			setUndoHistory(null);
			setApplyResult(
				`Moved ${result.updated} subscriptions to "${getCategoryLabel(batchCategory)}".`,
			);
			setSelected(new Set());
			router.refresh();
		} catch (err) {
			setApplyResult(`Action failed: ${getFlashMessage(toErrorCode(err))}`);
		} finally {
			setApplying(false);
		}
	}

	async function handleUndoCategory() {
		if (!undoContext) {
			return;
		}
		setUndoing(true);
		setApplyResult(null);
		try {
			const idsByCategory = new Map<SubscriptionCategory, string[]>();
			undoContext.ids.forEach((id) => {
				const oldCategory = undoContext.previousCategories[id];
				const bucket = idsByCategory.get(oldCategory) ?? [];
				bucket.push(id);
				idsByCategory.set(oldCategory, bucket);
			});

			await Promise.all(
				Array.from(idsByCategory.entries()).map(([category, ids]) =>
					batchUpdateWithAuth({ ids, category }),
				),
			);

			setVisibleSubscriptions((prev) =>
				prev.map((item) => {
					const previousCategory = undoContext.previousCategories[item.id];
					return previousCategory
						? { ...item, category: previousCategory }
						: item;
				}),
			);
			clearUndoContext();
			setUndoHistory({
				message: `Restored ${undoContext.ids.length} subscriptions to their previous categories.`,
				isError: false,
			});
			setApplyResult(
				`Category change undone. Restored ${undoContext.ids.length} subscriptions to their previous categories.`,
			);
			router.refresh();
		} catch (err) {
			setUndoHistory({
				message: "Undo failed. Please try again.",
				isError: true,
			});
			setApplyResult(`Undo failed: ${getFlashMessage(toErrorCode(err))}`);
		} finally {
			setUndoing(false);
		}
	}

	const allSelected =
		visibleSubscriptions.length > 0 &&
		selected.size === visibleSubscriptions.length;
	const partialSelection =
		selected.size > 0 && selected.size < visibleSubscriptions.length;
	const selectedSummary = `${selected.size}/${visibleSubscriptions.length}`;
	const isApplyError = Boolean(
		applyResult &&
			(applyResult.startsWith("Action failed") ||
				applyResult.startsWith("Delete failed") ||
				applyResult.startsWith("Undo failed")),
	);

	function getSubscriptionDisplayName(item: Subscription) {
		const sourceName = item.source_name?.trim();
		const sourceValue = item.source_value?.trim();
		return sourceName || sourceValue || `Subscription ${item.id}`;
	}

	function getSubscriptionDisplayNameById(id: string): string {
		const target = visibleSubscriptions.find((item) => item.id === id);
		return target ? getSubscriptionDisplayName(target) : `Subscription ${id}`;
	}

	if (visibleSubscriptions.length === 0) {
		return (
			<Card className="border-dashed">
				<CardHeader className="gap-2">
					<CardTitle className="text-base">Bulk subscription actions</CardTitle>
					<CardDescription>No subscriptions available.</CardDescription>
				</CardHeader>
			</Card>
		);
	}

	return (
		<Card className={editorialSans.className}>
			<CardHeader className="gap-2">
				<CardTitle className="text-base">Bulk subscription actions</CardTitle>
				<CardDescription>
					Review status, update categories in bulk, and confirm deletions
					safely.
				</CardDescription>
			</CardHeader>
			<CardContent className="space-y-4">
				<div className="overflow-x-auto rounded-lg border">
					<table className="min-w-[920px] w-full text-sm">
						<caption className="sr-only">Current subscriptions</caption>
						<thead className="bg-muted/40">
							<tr className="[&_th]:px-3 [&_th]:py-2.5 [&_th]:text-left [&_th]:text-xs [&_th]:font-medium [&_th]:text-muted-foreground">
								<th scope="col" className="w-12">
									<Checkbox
										checked={
											allSelected
												? true
												: partialSelection
													? "indeterminate"
													: false
										}
										onCheckedChange={toggleAll}
										aria-label={`Select all (${selectedSummary} selected)`}
									/>
								</th>
								<th scope="col">Source</th>
								<th scope="col">Platform / Type</th>
								<th scope="col">Category / Priority</th>
								<th scope="col">Enabled</th>
								<th scope="col">Updated</th>
								<th scope="col">Actions</th>
							</tr>
						</thead>
						<tbody>
							{visibleSubscriptions.map((item) => {
								const isSelected = selected.has(item.id);
								const rowState =
									deletingId === item.id
										? "deleting"
										: pendingDeleteId === item.id
											? "confirming-delete"
											: undefined;

								return (
									<tr
										key={item.id}
										className={cn(
											"border-b align-top transition-colors hover:bg-muted/20",
											isSelected && "row-selected bg-muted/35",
										)}
										data-state={rowState}
									>
										<td className="px-3 py-3">
											<Checkbox
												checked={isSelected}
												onCheckedChange={() => toggleOne(item.id)}
												aria-label={`Select ${getSubscriptionDisplayName(item)}`}
											/>
										</td>
										<td className="px-3 py-3">
											<div className="font-medium leading-5">
												<SourceIdentityCard
													identity={{
														...resolveSubscriptionIdentity(item),
														description:
															item.source_homepage_url ||
															item.source_url ||
															item.rsshub_route,
													}}
													compact
												/>
											</div>
										</td>
										<td className="px-3 py-3">
											<div>{item.platform}</div>
											<div className="text-xs text-muted-foreground">
												{humanizeSourceType(item.source_type)}
											</div>
										</td>
										<td className="px-3 py-3">
											<Badge
												variant={
													item.category === "misc" ? "outline" : "secondary"
												}
												className="sub-category-badge"
												data-category={item.category}
											>
												{getCategoryLabel(item.category)}
											</Badge>
											<div className="mt-1 text-xs text-muted-foreground">
												Priority {item.priority}
												{item.tags.length > 0
													? ` · ${item.tags.join(", ")}`
													: ""}
											</div>
										</td>
										<td className="px-3 py-3">
											<StatusBadge
												label={item.enabled ? "Enabled" : "Disabled"}
												tone={item.enabled ? "success" : "error"}
											/>
										</td>
										<td className="px-3 py-3 text-xs text-muted-foreground">
											<div>{formatDateTime(item.updated_at)}</div>
											<div className={editorialMono.className}>
												{item.id.slice(0, 8)}…
											</div>
										</td>
										<td className="px-3 py-3">
											{pendingDeleteId === item.id ? (
												<div className="inline-flex flex-wrap items-center gap-2">
													<Button
														ref={(element) => {
															confirmDeleteRefs.current[item.id] = element;
														}}
														type="button"
														variant="destructive"
														size="xs"
														disabled={deletingId === item.id}
														onClick={() => handleDeleteConfirm(item.id)}
														data-interaction="cta"
														data-testid="subscription-confirm-delete"
													>
														{deletingId === item.id
															? "Deleting..."
															: `Confirm delete "${getSubscriptionDisplayName(item)}"`}
													</Button>
													<Button
														type="button"
														variant="outline"
														size="xs"
														onClick={() => {
															restoreDeleteTriggerFocusIdRef.current = item.id;
															setPendingDeleteId(null);
															setDeleteStatusMessage("Delete cancelled.");
														}}
														data-interaction="control"
													>
														Cancel
													</Button>
												</div>
											) : (
												<Button
													ref={(element) => {
														deleteTriggerRefs.current[item.id] = element;
													}}
													type="button"
													variant="destructiveGhost"
													size="sm"
													disabled={deletingId === item.id}
													onClick={() => {
														setPendingDeleteId(item.id);
														setDeleteStatusMessage(
															`Delete confirmation opened for ${getSubscriptionDisplayName(item)}.`,
														);
													}}
													data-interaction="cta"
												>
													Delete
												</Button>
											)}
										</td>
									</tr>
								);
							})}
						</tbody>
					</table>
				</div>

				{selected.size > 0 && (
					<div className="batch-action-bar rounded-lg border bg-muted/25 p-3">
						<div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
							<span className="text-sm text-muted-foreground">
								Selected{" "}
								<strong className="text-foreground">{selected.size}</strong>{" "}
								subscriptions
							</span>
							<div className="inline-flex flex-wrap items-center gap-2">
								<Label
									htmlFor="batch-category"
									className="batch-category-label text-xs font-medium"
								>
									Bulk category
								</Label>
								<Select
									value={batchCategory}
									onValueChange={(value) =>
										setBatchCategory(value as SubscriptionCategory)
									}
								>
									<SelectTrigger
										id="batch-category"
										aria-label="Bulk category"
										className="min-w-[9rem]"
									>
										<SelectValue placeholder="Select category" />
									</SelectTrigger>
									<SelectContent>
										{CATEGORIES.map((c) => (
											<SelectItem key={c} value={c}>
												{getCategoryLabel(c)}
											</SelectItem>
										))}
									</SelectContent>
								</Select>
								<Button
									type="button"
									disabled={applying || undoing}
									onClick={handleApplyCategory}
									data-interaction="cta"
									data-feedback-state={applying ? "pending" : "idle"}
									aria-busy={applying}
									data-testid="subscription-apply-category"
								>
									{applying ? "Applying..." : "Apply category"}
								</Button>
								<Button
									type="button"
									variant="outline"
									onClick={() => setSelected(new Set())}
									data-interaction="control"
								>
									Clear selection
								</Button>
							</div>
						</div>
					</div>
				)}

				{applyResult &&
					(isApplyError ? (
						<p
							className="alert mt-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
							role="alert"
							aria-live="assertive"
							aria-atomic="true"
						>
							{applyResult}
						</p>
					) : (
						<output
							className="alert mt-2 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700 dark:text-emerald-300"
							aria-live="polite"
							aria-atomic="true"
						>
							{applyResult}
						</output>
					))}

				{undoContext && (
					<div
						className="alert flex flex-wrap items-center gap-2 rounded-md border border-border bg-muted/20 px-3 py-2 text-sm"
						aria-live="polite"
						aria-atomic="true"
					>
						<span>
							Updated {undoContext.ids.length} subscriptions to &quot;
							{getCategoryLabel(undoContext.nextCategory)}&quot;. Undo available
							for {undoRemainingSeconds} seconds.
						</span>
						<Button
							type="button"
							variant="link"
							size="sm"
							className="h-auto p-0"
							onClick={handleUndoCategory}
							disabled={undoing || applying}
							data-interaction="control"
							data-testid="subscription-undo-category"
						>
							{undoing ? "Undoing..." : "Undo"}
						</Button>
					</div>
				)}

				{undoHistory &&
					(undoHistory.isError ? (
						<p
							className="alert rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
							role="alert"
							aria-live="assertive"
							aria-atomic="true"
						>
							{undoHistory.message}
						</p>
					) : (
						<output
							className="alert rounded-md border border-border bg-muted/20 px-3 py-2 text-sm"
							aria-live="polite"
							aria-atomic="true"
						>
							{undoHistory.message}
						</output>
					))}

				<output className="sr-only" aria-live="polite" aria-atomic="true">
					{deleteStatusMessage}
				</output>
			</CardContent>
		</Card>
	);
}
