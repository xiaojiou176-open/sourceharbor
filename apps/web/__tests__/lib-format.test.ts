import { describe, expect, it } from "vitest";

import {
	formatDateTime,
	formatDateTimeWithSeconds,
	toNumber,
} from "@/lib/format";

describe("format helpers", () => {
	it("returns placeholder for empty date inputs", () => {
		expect(formatDateTime(null)).toBe("-");
		expect(formatDateTime(undefined)).toBe("-");
		expect(formatDateTime("")).toBe("-");
		expect(formatDateTimeWithSeconds(null)).toBe("-");
	});

	it("returns raw input for invalid date strings", () => {
		expect(formatDateTime("not-a-date")).toBe("not-a-date");
		expect(formatDateTimeWithSeconds("broken")).toBe("broken");
	});

	it("formats valid date strings", () => {
		const iso = "2026-02-01T08:09:10Z";
		expect(formatDateTime(iso)).toContain("2026");
		expect(formatDateTimeWithSeconds(iso)).toContain("2026");
		expect(formatDateTimeWithSeconds(iso)).not.toBe("-");
	});
});

describe("toNumber", () => {
	it("accepts finite numbers and numeric strings", () => {
		expect(toNumber(12)).toBe(12);
		expect(toNumber(" 12.5 ")).toBe(12.5);
		expect(toNumber("0")).toBe(0);
	});

	it("uses fallback for invalid values", () => {
		expect(toNumber(Number.NaN, 3)).toBe(3);
		expect(toNumber(Infinity, 3)).toBe(3);
		expect(toNumber("x", 3)).toBe(3);
		expect(toNumber("   ", 7)).toBe(7);
		expect(toNumber({}, 9)).toBe(9);
	});
});
