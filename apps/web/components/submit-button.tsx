"use client";

import type { ComponentProps } from "react";
import { useId } from "react";
import { useFormStatus } from "react-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getLocaleMessages } from "@/lib/i18n/messages";
import { cn } from "@/lib/utils";

type SubmitButtonProps = Omit<
	ComponentProps<typeof Button>,
	"type" | "disabled"
> & {
	pendingLabel?: string;
	statusText?: string;
};

export function SubmitButton({
	children,
	className,
	pendingLabel,
	statusText,
	"aria-describedby": ariaDescribedBy,
	...props
}: SubmitButtonProps) {
	const copy = getLocaleMessages().submitButton;
	const { pending } = useFormStatus();
	const statusId = useId();
	const state = pending ? "pending" : "idle";
	const resolvedPendingLabel = pendingLabel ?? "Submitting…";
	const buttonLabel = pending ? (
		<span
			className="inline-flex items-center gap-2"
			data-part="button-content"
			data-state={state}
		>
			<Badge
				variant="secondary"
				className="rounded-full bg-primary-foreground/18 px-1.5 py-0 text-[10px] font-semibold text-primary-foreground"
				data-part="pending-indicator"
				data-state={state}
				aria-hidden="true"
			>
				{copy.pendingBadge}
			</Badge>
			<span data-part="button-label" data-state={state}>
				{resolvedPendingLabel}
			</span>
			<span className="sr-only">{copy.pendingSrOnly}</span>
		</span>
	) : (
		<span
			className="inline-flex items-center gap-2"
			data-part="button-content"
			data-state={state}
		>
			<span data-part="button-label" data-state={state}>
				{children}
			</span>
		</span>
	);
	const pendingStatusText = statusText ?? resolvedPendingLabel;
	const buttonClassName = cn("min-w-[8.5rem] rounded-xl shadow-sm", className);
	const describedBy =
		[ariaDescribedBy, statusId].filter(Boolean).join(" ") || undefined;

	return (
		<>
			<Button
				{...props}
				type="submit"
				className={buttonClassName}
				disabled={pending}
				aria-disabled={pending}
				aria-busy={pending}
				aria-describedby={describedBy}
				data-state={state}
				data-feedback-state={state}
				data-interaction="cta"
				suppressHydrationWarning
			>
				{buttonLabel}
			</Button>
			<output
				id={statusId}
				className="sr-only"
				aria-live="polite"
				aria-atomic="true"
			>
				{pending ? pendingStatusText : ""}
			</output>
		</>
	);
}
