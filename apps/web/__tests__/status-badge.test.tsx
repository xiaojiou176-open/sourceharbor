import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { mapStatusCssToTone, StatusBadge } from "@/components/status-badge";

describe("StatusBadge", () => {
	it("maps common backend statuses to tones", () => {
		expect(mapStatusCssToTone(undefined)).toBe("idle");
		expect(mapStatusCssToTone("queued")).toBe("pending");
		expect(mapStatusCssToTone("running")).toBe("running");
		expect(mapStatusCssToTone("succeeded")).toBe("success");
		expect(mapStatusCssToTone("degraded")).toBe("warning");
		expect(mapStatusCssToTone("failed")).toBe("error");
		expect(mapStatusCssToTone("something-else")).toBe("idle");
	});

	it("renders the matching tone classes", () => {
		render(<StatusBadge label="执行中" tone="running" />);
		expect(screen.getByText("执行中")).toHaveClass("border-amber-500/20");
	});
});
