import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type StatusTone =
	| "idle"
	| "pending"
	| "running"
	| "success"
	| "warning"
	| "error";

type StatusBadgeProps = {
	label: string;
	tone: StatusTone;
	className?: string;
};

const toneClassMap: Record<StatusTone, string> = {
	idle: "border-border/70 bg-background text-muted-foreground",
	pending: "border-primary/20 bg-primary/8 text-primary",
	running:
		"border-amber-500/20 bg-amber-500/10 text-amber-700 dark:text-amber-300",
	success:
		"border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
	warning:
		"border-orange-500/20 bg-orange-500/10 text-orange-700 dark:text-orange-300",
	error: "border-destructive/20 bg-destructive/10 text-destructive",
};

const statusToneMap: Record<string, StatusTone> = {
	pending: "pending",
	queued: "pending",
	running: "running",
	succeeded: "success",
	completed: "success",
	enabled: "success",
	degraded: "warning",
	skipped: "warning",
	failed: "error",
	error: "error",
	cancelled: "error",
};

export function mapStatusCssToTone(
	statusCss: string | null | undefined,
): StatusTone {
	if (!statusCss) {
		return "idle";
	}
	const normalized = statusCss.trim().toLowerCase();
	return statusToneMap[normalized] ?? "idle";
}

export function StatusBadge({ label, tone, className }: StatusBadgeProps) {
	return (
		<Badge
			variant="outline"
			className={cn(
				"rounded-full px-2 py-0.5 text-[11px] font-semibold tracking-[0.01em]",
				toneClassMap[tone],
				className,
			)}
		>
			{label}
		</Badge>
	);
}
