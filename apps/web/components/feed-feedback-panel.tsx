"use client";

import { startTransition, useState } from "react";

import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api/client";
import type { FeedFeedback } from "@/lib/api/types";
import { resolveWriteSessionToken } from "@/lib/api/url";

type FeedbackLabel = "useful" | "noisy" | "dismissed" | "archived" | null;

type FeedFeedbackPanelProps = {
	initialFeedback: FeedFeedback | null;
	jobId: string;
	sessionToken?: string;
};

function describeFeedback(feedback: FeedFeedback | null): string {
	if (!feedback || !feedback.exists) {
		return "No curation signal recorded yet.";
	}
	if (feedback.saved && feedback.feedback_label === "useful") {
		return "Marked as saved and useful.";
	}
	if (feedback.saved) {
		return "Marked as saved.";
	}
	if (feedback.feedback_label === "noisy") {
		return "Marked as noisy.";
	}
	if (feedback.feedback_label === "dismissed") {
		return "Marked as dismissed.";
	}
	if (feedback.feedback_label === "archived") {
		return "Marked as archived.";
	}
	return "Feedback updated.";
}

export function FeedFeedbackPanel({
	initialFeedback,
	jobId,
	sessionToken,
}: FeedFeedbackPanelProps) {
	const effectiveSessionToken = resolveWriteSessionToken(sessionToken);
	const [feedback, setFeedback] = useState<FeedFeedback | null>(
		initialFeedback,
	);
	const [pending, setPending] = useState<FeedbackLabel | "save" | null>(null);
	const [error, setError] = useState<string | null>(null);

	function submit(saved: boolean, feedbackLabel: FeedbackLabel) {
		setPending(feedbackLabel ?? "save");
		setError(null);
		startTransition(() => {
			apiClient
				.updateFeedFeedback(
					{
						job_id: jobId,
						saved,
						feedback_label: feedbackLabel,
					},
					{ webSessionToken: effectiveSessionToken },
				)
				.then((payload) => {
					setFeedback(payload);
				})
				.catch(() => {
					setError("Feedback update failed. Please retry.");
				})
				.finally(() => {
					setPending(null);
				});
		});
	}

	return (
		<section className="folo-panel folo-surface" aria-label="Digest feedback">
			<div className="space-y-2">
				<p className="text-sm font-medium">Feed curation</p>
				<p className="text-sm text-muted-foreground">
					Use these signals to tell SourceHarbor what should stay, what was
					useful, and what should be filtered out later.
				</p>
				<p
					className="text-xs text-muted-foreground"
					role={error ? "alert" : "status"}
					aria-live={error ? "assertive" : "polite"}
				>
					{error ?? describeFeedback(feedback)}
				</p>
			</div>
			<div className="mt-3 flex flex-wrap gap-2">
				<Button
					type="button"
					size="sm"
					variant={feedback?.saved ? "success" : "outline"}
					disabled={pending !== null}
					onClick={() => submit(true, feedback?.feedback_label ?? "useful")}
				>
					{pending === "save" ? "Saving…" : "Save"}
				</Button>
				<Button
					type="button"
					size="sm"
					variant={
						feedback?.feedback_label === "useful" ? "success" : "outline"
					}
					disabled={pending !== null}
					onClick={() => submit(true, "useful")}
				>
					{pending === "useful" ? "Updating…" : "Useful"}
				</Button>
				<Button
					type="button"
					size="sm"
					variant={
						feedback?.feedback_label === "noisy" ? "destructive" : "outline"
					}
					disabled={pending !== null}
					onClick={() => submit(false, "noisy")}
				>
					{pending === "noisy" ? "Updating…" : "Noisy"}
				</Button>
				<Button
					type="button"
					size="sm"
					variant={
						feedback?.feedback_label === "dismissed" ? "secondary" : "outline"
					}
					disabled={pending !== null}
					onClick={() => submit(false, "dismissed")}
				>
					{pending === "dismissed" ? "Updating…" : "Dismiss"}
				</Button>
			</div>
		</section>
	);
}
