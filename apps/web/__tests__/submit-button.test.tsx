import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { useFormStatusMock } = vi.hoisted(() => ({
	useFormStatusMock: vi.fn(),
}));

vi.mock("react-dom", async () => {
	const actual = await vi.importActual<typeof import("react-dom")>("react-dom");
	return {
		...actual,
		useFormStatus: useFormStatusMock,
	};
});

import { SubmitButton } from "@/components/submit-button";

describe("SubmitButton", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		useFormStatusMock.mockReturnValue({ pending: false });
	});

	it("renders idle submit state with composed aria-describedby", () => {
		render(
			<SubmitButton aria-describedby="external-help" className="primary">
				Save configuration
			</SubmitButton>,
		);

		const button = screen.getByRole("button", { name: "Save configuration" });
		const statusOutput = screen.getByRole("status");
		const describedBy = button.getAttribute("aria-describedby") ?? "";

		expect(button).toHaveAttribute("type", "submit");
		expect(button).toHaveAttribute("data-slot", "button");
		expect(button).toHaveAttribute("data-state", "idle");
		expect(button).toHaveAttribute("aria-disabled", "false");
		expect(button).toHaveAttribute("aria-busy", "false");
		expect(describedBy).toContain("external-help");
		expect(describedBy).toContain(statusOutput.id);
		expect(statusOutput).toBeEmptyDOMElement();
	});

	it("renders pending feedback state and announces provided status text", () => {
		useFormStatusMock.mockReturnValue({ pending: true });

		render(
			<SubmitButton
				pendingLabel="Saving…"
				statusText="Saving notification settings. Please wait."
			>
				Save configuration
			</SubmitButton>,
		);

		const button = screen.getByRole("button");
		const statusOutput = screen.getByRole("status");

		expect(button).toBeDisabled();
		expect(button).toHaveAttribute("data-state", "pending");
		expect(button).toHaveAttribute("aria-disabled", "true");
		expect(button).toHaveAttribute("aria-busy", "true");
		expect(button).toHaveAttribute("data-feedback-state", "pending");
		expect(within(button).getByText("Saving…")).toBeInTheDocument();
		expect(within(button).getByText("Submitting. Please wait.")).toHaveClass(
			"sr-only",
		);
		expect(statusOutput).toHaveTextContent(
			"Saving notification settings. Please wait.",
		);
	});

	it("falls back to pending label when statusText is omitted", () => {
		useFormStatusMock.mockReturnValue({ pending: true });

		render(
			<SubmitButton pendingLabel="Creating job…">
				Start processing
			</SubmitButton>,
		);

		expect(screen.getByRole("status")).toHaveTextContent("Creating job…");
	});
});
