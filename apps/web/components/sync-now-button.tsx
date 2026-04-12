"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api/client";
import { resolveWriteSessionToken } from "@/lib/api/url";
import { getLocaleMessages } from "@/lib/i18n/messages";
import { cn } from "@/lib/utils";

type SyncNowButtonProps = {
	sessionToken?: string;
};

export function SyncNowButton({ sessionToken }: SyncNowButtonProps) {
	const effectiveSessionToken = resolveWriteSessionToken(sessionToken);
	const copy = getLocaleMessages().syncNow;
	const [state, setState] = useState<"idle" | "loading" | "done" | "error">(
		"idle",
	);
	const router = useRouter();
	const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
	const isLoading = state === "loading";
	const feedbackMap = {
		idle: {
			...copy.idle,
			liveMode: "polite" as const,
			badgeVariant: "outline" as const,
		},
		loading: {
			...copy.loading,
			liveMode: "polite" as const,
			badgeVariant: "secondary" as const,
		},
		done: {
			...copy.done,
			liveMode: "polite" as const,
			badgeVariant: "secondary" as const,
		},
		error: {
			...copy.error,
			liveMode: "assertive" as const,
			badgeVariant: "destructive" as const,
		},
	};
	const feedback = feedbackMap[state];
	const buttonVariant =
		state === "loading"
			? "secondary"
			: state === "done"
				? "success"
				: state === "error"
					? "destructive"
					: "hero";
	const liveStatusLabel =
		state === "loading"
			? copy.loading.liveStatusLabel
			: state === "done"
				? copy.done.liveStatusLabel
				: state === "error"
					? copy.error.liveStatusLabel
					: "";
	const hintClassName = cn(
		"text-xs leading-5 text-muted-foreground transition-colors duration-200",
		state === "loading" && "text-amber-700 dark:text-amber-300",
		state === "done" && "text-emerald-700 dark:text-emerald-300",
		state === "error" && "text-destructive",
	);
	const clearTimer = useCallback(() => {
		if (!timerRef.current) {
			return;
		}
		clearTimeout(timerRef.current);
		timerRef.current = null;
	}, []);

	useEffect(() => {
		return () => {
			clearTimer();
		};
	}, [clearTimer]);

	function handleSync() {
		setState("loading");
		clearTimer();
		const request = effectiveSessionToken
			? apiClient.pollIngest({}, { webSessionToken: effectiveSessionToken })
			: apiClient.pollIngest({});
		request
			.then(() => {
				timerRef.current = setTimeout(() => {
					setState("done");
					timerRef.current = setTimeout(() => {
						setState("idle");
						router.refresh();
					}, 1500);
				}, 0);
			})
			.catch(() => {
				setState("error");
			});
	}

	return (
		<>
			<Button
				type="button"
				onClick={handleSync}
				disabled={isLoading}
				variant={buttonVariant}
				className={cn(
					"min-w-[13rem] justify-between rounded-xl",
					!isLoading && "card-interactive",
				)}
				aria-describedby="sync-now-status"
				aria-disabled={isLoading}
				aria-busy={isLoading}
				data-state={state}
				data-feedback-state={state}
				data-interaction="cta"
				title={state === "error" ? copy.error.retryTitle : undefined}
			>
				<span
					className="inline-flex items-center gap-2"
					data-part="button-content"
					data-state={state}
				>
					<Badge
						variant={feedback.badgeVariant}
						className={cn(
							"rounded-full px-1.5 py-0 text-[10px] font-semibold",
							state === "idle" &&
								"border-white/30 bg-white/12 text-white dark:border-white/20 dark:bg-white/10",
						)}
						data-part="state-badge"
						data-state={state}
						aria-hidden="true"
					>
						{feedback.badgeLabel}
					</Badge>
					<span data-part="button-label" data-state={state}>
						{feedback.buttonLabel}
					</span>
					{isLoading ? (
						<span className="sr-only" aria-hidden="true">
							{copy.loading.liveStatusLabel}
						</span>
					) : null}
				</span>
			</Button>
			<p
				className={hintClassName}
				data-part="status-hint"
				data-state={state}
				data-feedback-state={state}
				aria-hidden="true"
			>
				{feedback.statusLabel}
			</p>
			<output
				id="sync-now-status"
				className="sr-only"
				role={state === "error" ? "alert" : "status"}
				aria-live={feedback.liveMode}
				aria-atomic="true"
				data-part="status-live"
				data-state={state}
				data-feedback-state={state}
			>
				{liveStatusLabel}
			</output>
		</>
	);
}
