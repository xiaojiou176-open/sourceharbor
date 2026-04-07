export type DisplayStatus = {
	css: string;
	label: string;
};

const LABEL_MAP: Record<string, string> = {
	running: "Running",
	queued: "Queued",
	succeeded: "Succeeded",
	failed: "Failed",
	degraded: "Degraded",
	pending: "Pending",
	cancelled: "Cancelled",
	skipped: "Skipped",
};

export function toDisplayStatus(
	rawStatus: string | null | undefined,
): DisplayStatus {
	const normalized = (rawStatus ?? "").trim().toLowerCase();
	if (!normalized) {
		return { css: "queued", label: "-" };
	}
	return { css: normalized, label: LABEL_MAP[normalized] ?? normalized };
}
