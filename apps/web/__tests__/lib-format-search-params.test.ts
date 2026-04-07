import { describe, expect, it } from "vitest";

import {
	formatDateTime,
	formatDateTimeWithSeconds,
	toNumber,
} from "@/lib/format";
import { resolveSearchParams } from "@/lib/search-params";

describe("format helpers", () => {
	it("formats datetime and falls back for empty/invalid inputs", () => {
		expect(formatDateTime(null)).toBe("-");
		expect(formatDateTime("not-a-date")).toBe("not-a-date");
		expect(formatDateTime("2026-02-26T03:04:05Z")).toContain("2026");

		expect(formatDateTimeWithSeconds(undefined)).toBe("-");
		expect(formatDateTimeWithSeconds("invalid")).toBe("invalid");
		expect(formatDateTimeWithSeconds("2026-02-26T03:04:05Z")).toContain("2026");
	});

	it("parses finite number values and applies fallback", () => {
		expect(toNumber(42)).toBe(42);
		expect(toNumber("3.14")).toBe(3.14);
		expect(toNumber("", 7)).toBe(7);
		expect(toNumber("abc", 9)).toBe(9);
		expect(toNumber(Infinity, 11)).toBe(11);
	});
});

describe("resolveSearchParams", () => {
	it("normalizes scalar/array/missing values", async () => {
		const resolved = await resolveSearchParams(
			Promise.resolve({
				source: " youtube ",
				category: ["", "tech"],
				limit: undefined,
			}),
			["source", "category", "limit"] as const,
		);

		expect(resolved).toEqual({
			source: "youtube",
			category: "",
			limit: "",
		});
	});
});
