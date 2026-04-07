export function formatDateTime(input: string | null | undefined): string {
	if (!input) {
		return "-";
	}

	const date = new Date(input);
	if (Number.isNaN(date.getTime())) {
		return input;
	}

	return new Intl.DateTimeFormat("en-US", {
		dateStyle: "medium",
		timeStyle: "short",
	}).format(date);
}

export function formatDateTimeWithSeconds(
	input: string | null | undefined,
): string {
	if (!input) {
		return "-";
	}

	const date = new Date(input);
	if (Number.isNaN(date.getTime())) {
		return input;
	}

	return new Intl.DateTimeFormat("en-US", {
		dateStyle: "medium",
		timeStyle: "medium",
	}).format(date);
}

export function toNumber(value: unknown, fallback = 0): number {
	if (typeof value === "number" && Number.isFinite(value)) {
		return value;
	}
	if (typeof value === "string" && value.trim()) {
		const parsed = Number(value);
		if (Number.isFinite(parsed)) {
			return parsed;
		}
	}
	return fallback;
}
