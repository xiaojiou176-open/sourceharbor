"use client";

import { useEffect, useState } from "react";
import { formatCountPattern, getLocaleMessages } from "@/lib/i18n/messages";

type Props = {
	dateTime: string;
};

function formatRelative(dateTime: string): string {
	const copy = getLocaleMessages().relativeTime;
	const date = new Date(dateTime);
	if (Number.isNaN(date.getTime())) {
		return dateTime;
	}

	const diffMs = Date.now() - date.getTime();
	if (diffMs < 0) {
		const futureSec = Math.floor(Math.abs(diffMs) / 1000);
		const futureMin = Math.floor(futureSec / 60);
		const futureHour = Math.floor(futureMin / 60);
		const futureDay = Math.floor(futureHour / 24);

		if (futureSec < 60) {
			return copy.soon;
		}
		if (futureMin < 60) {
			return formatCountPattern(copy.minuteFuture, Math.max(1, futureMin));
		}
		if (futureHour < 24) {
			return formatCountPattern(copy.hourFuture, Math.max(1, futureHour));
		}
		if (futureDay < 2) {
			return copy.tomorrow;
		}
		if (futureDay < 7) {
			return formatCountPattern(copy.dayFuture, futureDay);
		}
		if (futureDay < 30) {
			return formatCountPattern(copy.weekFuture, Math.floor(futureDay / 7));
		}
		if (futureDay < 365) {
			return formatCountPattern(copy.monthFuture, Math.floor(futureDay / 30));
		}
		return formatCountPattern(copy.yearFuture, Math.floor(futureDay / 365));
	}

	const diffSec = Math.floor(diffMs / 1000);
	const diffMin = Math.floor(diffSec / 60);
	const diffHour = Math.floor(diffMin / 60);
	const diffDay = Math.floor(diffHour / 24);

	if (diffSec < 60) {
		return copy.justNow;
	}
	if (diffMin < 60) {
		return formatCountPattern(copy.minutePast, diffMin);
	}
	if (diffHour < 24) {
		return formatCountPattern(copy.hourPast, diffHour);
	}
	if (diffDay < 7) {
		return formatCountPattern(copy.dayPast, diffDay);
	}
	if (diffDay < 30) {
		return formatCountPattern(copy.weekPast, Math.floor(diffDay / 7));
	}
	if (diffDay < 365) {
		return formatCountPattern(copy.monthPast, Math.floor(diffDay / 30));
	}
	return formatCountPattern(copy.yearPast, Math.floor(diffDay / 365));
}

function formatAbsolute(dateTime: string): string {
	const copy = getLocaleMessages().relativeTime;
	const date = new Date(dateTime);
	if (Number.isNaN(date.getTime())) {
		return dateTime;
	}
	return date.toLocaleString(copy.absoluteLocale, {
		year: "numeric",
		month: "2-digit",
		day: "2-digit",
		hour: "2-digit",
		minute: "2-digit",
	});
}

export function RelativeTime({ dateTime }: Props) {
	const [relative, setRelative] = useState<string>(() =>
		formatRelative(dateTime),
	);
	const absolute = formatAbsolute(dateTime);

	useEffect(() => {
		const timer = setInterval(
			() => setRelative(formatRelative(dateTime)),
			60_000,
		);
		return () => clearInterval(timer);
	}, [dateTime]);

	return (
		<time dateTime={dateTime} title={absolute} className="relative-time">
			{relative}
		</time>
	);
}
