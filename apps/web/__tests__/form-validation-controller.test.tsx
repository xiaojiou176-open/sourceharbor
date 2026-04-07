import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { usePathnameMock } = vi.hoisted(() => ({
	usePathnameMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
	usePathname: usePathnameMock,
}));

import { FormValidationController } from "@/components/form-validation-controller";

describe("FormValidationController", () => {
	beforeEach(() => {
		usePathnameMock.mockReturnValue("/");
	});

	it("disables submit until required fields are valid", () => {
		render(
			<>
				<FormValidationController />
				<form data-auto-disable-required="true">
					<input aria-label="name" name="name" required defaultValue="" />
					<button type="submit">Submit</button>
				</form>
			</>,
		);

		const button = screen.getByRole("button", { name: "Submit" });
		expect(button).toBeDisabled();
		expect(button).toHaveAttribute("aria-disabled", "true");
		const requiredReason = screen.getByRole("alert");
		expect(requiredReason).toHaveTextContent(
			"Fill in and fix the required fields before submitting.",
		);
		expect(requiredReason).toBeVisible();
		expect(requiredReason).toHaveAttribute("aria-live", "assertive");
		expect(button).toHaveAttribute(
			"title",
			"Fill in and fix the required fields before submitting.",
		);
		expect(button).toHaveAttribute("aria-describedby", requiredReason.id);

		const input = screen.getByLabelText("name");
		fireEvent.input(input, { target: { value: "Alice" } });

		expect(button).not.toBeDisabled();
		expect(button).toHaveAttribute("aria-disabled", "false");
		expect(requiredReason).toBeEmptyDOMElement();
		expect(requiredReason).not.toBeVisible();
		expect(button).not.toHaveAttribute("aria-describedby");
		expect(button).not.toHaveAttribute("title");
	});

	it("enforces require-one and exclusive mode", () => {
		render(
			<>
				<FormValidationController />
				<form data-require-one="url,video_id" data-require-one-exclusive="true">
					<input aria-label="url" name="url" defaultValue="" />
					<input aria-label="video" name="video_id" defaultValue="" />
					<button type="submit">Run</button>
				</form>
			</>,
		);

		const submit = screen.getByRole("button", { name: "Run" });
		const url = screen.getByLabelText("url");
		const video = screen.getByLabelText("video");
		const reason = screen.getByRole("alert");

		expect(submit).toBeDisabled();
		expect(reason).toHaveTextContent(
			"Fill in at least one required source before submitting.",
		);
		expect(reason).toBeVisible();
		expect(submit).toHaveAttribute("aria-describedby", reason.id);
		expect(reason).toHaveAttribute("aria-live", "assertive");
		expect(submit).toHaveAttribute(
			"title",
			"Fill in at least one required source before submitting.",
		);

		fireEvent.input(url, { target: { value: "https://example.com/video" } });
		expect(submit).not.toBeDisabled();
		expect(reason).toBeEmptyDOMElement();
		expect(reason).not.toBeVisible();
		expect(submit).not.toHaveAttribute("aria-describedby");
		expect(submit).not.toHaveAttribute("title");

		fireEvent.input(video, { target: { value: "abc" } });
		expect(submit).toBeDisabled();
		expect(reason).toHaveTextContent(
			"Only one source can be filled right now. Clear the extra inputs before submitting.",
		);
		expect(reason).toBeVisible();
		expect(submit).toHaveAttribute("aria-describedby", reason.id);
		expect(submit).toHaveAttribute(
			"title",
			"Only one source can be filled right now. Clear the extra inputs before submitting.",
		);
	});

	it("toggles dependent fields by checkbox controller", () => {
		render(
			<>
				<FormValidationController />
				<form>
					<label>
						<input type="checkbox" name="enabled" aria-label="enabled" />
						Enable
					</label>
					<input
						name="email"
						aria-label="email"
						data-disabled-unless-checked="enabled"
						defaultValue="a@example.com"
					/>
					<button type="submit">Save</button>
				</form>
			</>,
		);

		const email = screen.getByLabelText("email") as HTMLInputElement;
		const enabled = screen.getByLabelText("enabled");

		expect(email.disabled).toBe(true);
		expect(email).toHaveAttribute("aria-disabled", "true");

		fireEvent.change(enabled, { target: { checked: true } });

		expect(email.disabled).toBe(false);
		expect(email).toHaveAttribute("aria-disabled", "false");
	});

	it("ignores forms without a submit control", () => {
		render(
			<>
				<FormValidationController />
				<form data-auto-disable-required="true">
					<input
						aria-label="standalone-required"
						name="name"
						required
						defaultValue=""
					/>
				</form>
			</>,
		);

		const input = screen.getByLabelText("standalone-required");
		fireEvent.input(input, { target: { value: "ok" } });
		expect(input).toHaveValue("ok");
	});

	it("ignores non-element input events and empty dependent controller names", () => {
		render(
			<>
				<FormValidationController />
				<form>
					<input
						name="email"
						aria-label="email-with-empty-controller"
						data-disabled-unless-checked=""
						defaultValue="a@example.com"
					/>
					<button type="submit">Save</button>
				</form>
			</>,
		);

		const email = screen.getByLabelText("email-with-empty-controller");
		fireEvent(
			document,
			new Event("input", {
				bubbles: true,
				cancelable: true,
			}),
		);
		expect(email).toHaveValue("a@example.com");
	});
});
