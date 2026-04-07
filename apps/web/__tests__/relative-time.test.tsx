import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RelativeTime } from "@/components/relative-time";

describe("RelativeTime", () => {
	beforeEach(() => {
		vi.useFakeTimers();
		vi.setSystemTime(new Date("2026-02-26T12:00:00Z"));
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it("shows fallback text when date is invalid", () => {
		render(<RelativeTime dateTime="not-a-date" />);

		expect(screen.getByText("not-a-date")).toBeInTheDocument();
		expect(screen.getByTitle("not-a-date")).toBeInTheDocument();
	});

	it("formats minute/hour/day/week/month/year buckets", () => {
		const minute = render(<RelativeTime dateTime="2026-02-26T11:59:40Z" />);
		expect(screen.getByText("刚刚")).toBeInTheDocument();
		minute.unmount();

		const hour = render(<RelativeTime dateTime="2026-02-26T10:00:00Z" />);
		expect(screen.getByText("2 小时前")).toBeInTheDocument();
		hour.unmount();

		const day = render(<RelativeTime dateTime="2026-02-20T12:00:00Z" />);
		expect(screen.getByText("6 天前")).toBeInTheDocument();
		day.unmount();

		const week = render(<RelativeTime dateTime="2026-02-10T12:00:00Z" />);
		expect(screen.getByText("2 周前")).toBeInTheDocument();
		week.unmount();

		const month = render(<RelativeTime dateTime="2025-12-10T12:00:00Z" />);
		expect(screen.getByText("2 个月前")).toBeInTheDocument();
		month.unmount();

		render(<RelativeTime dateTime="2024-12-10T12:00:00Z" />);
		expect(screen.getByText("1 年前")).toBeInTheDocument();
	});

	it("formats future minute/hour/tomorrow/day/week/month/year buckets", () => {
		const minute = render(<RelativeTime dateTime="2026-02-26T12:00:30Z" />);
		expect(screen.getByText("马上")).toBeInTheDocument();
		minute.unmount();

		const hour = render(<RelativeTime dateTime="2026-02-26T14:00:00Z" />);
		expect(screen.getByText("2 小时后")).toBeInTheDocument();
		hour.unmount();

		const tomorrow = render(<RelativeTime dateTime="2026-02-27T12:00:00Z" />);
		expect(screen.getByText("明天")).toBeInTheDocument();
		tomorrow.unmount();

		const day = render(<RelativeTime dateTime="2026-03-02T12:00:00Z" />);
		expect(screen.getByText("4 天后")).toBeInTheDocument();
		day.unmount();

		const week = render(<RelativeTime dateTime="2026-03-12T12:00:00Z" />);
		expect(screen.getByText("2 周后")).toBeInTheDocument();
		week.unmount();

		const month = render(<RelativeTime dateTime="2026-04-26T12:00:00Z" />);
		expect(screen.getByText("1 个月后")).toBeInTheDocument();
		month.unmount();

		render(<RelativeTime dateTime="2027-02-26T12:00:00Z" />);
		expect(screen.getByText("1 年后")).toBeInTheDocument();
	});

	it("recomputes text on interval ticks", () => {
		render(<RelativeTime dateTime="2026-02-26T11:59:30Z" />);
		expect(screen.getByText("刚刚")).toBeInTheDocument();

		act(() => {
			vi.advanceTimersByTime(61_000);
		});

		expect(screen.getByText("1 分钟前")).toBeInTheDocument();
	});
});
