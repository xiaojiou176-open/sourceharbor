import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FormValidationController } from "@/components/form-validation-controller";
import { RelativeTime } from "@/components/relative-time";

describe("RelativeTime", () => {
	beforeEach(() => {
		vi.useFakeTimers();
		vi.setSystemTime(new Date("2026-02-26T00:10:00Z"));
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it("renders relative text and keeps datetime/title attributes", () => {
		render(<RelativeTime dateTime="2026-02-26T00:09:30Z" />);

		const time = screen.getByText("just now");
		expect(time.tagName.toLowerCase()).toBe("time");
		expect(time).toHaveAttribute("datetime", "2026-02-26T00:09:30Z");
		expect(time).toHaveAttribute("title");
	});

	it("updates rendered text on interval tick", () => {
		render(<RelativeTime dateTime="2026-02-25T23:00:00Z" />);

		expect(screen.getByText("1 hour ago")).toBeInTheDocument();

		act(() => {
			vi.advanceTimersByTime(60_000);
		});

		expect(screen.getByText("1 hour ago")).toBeInTheDocument();

		act(() => {
			vi.setSystemTime(new Date("2026-02-26T02:10:00Z"));
			vi.advanceTimersByTime(60_000);
		});

		expect(screen.getByText("3 hours ago")).toBeInTheDocument();
	});

	it("falls back to raw input when date is invalid", () => {
		render(<RelativeTime dateTime="invalid-date" />);

		expect(screen.getByText("invalid-date")).toBeInTheDocument();
	});
});

describe("FormValidationController", () => {
	beforeEach(() => {
		document.body.innerHTML = "";
	});

	it("disables submit while required field is blank then enables after valid input", () => {
		render(
			<>
				<form data-auto-disable-required="true">
					<input name="url" type="url" required />
					<button type="submit">Submit</button>
				</form>
				<FormValidationController />
			</>,
		);

		const submit = screen.getByRole("button", { name: "Submit" });
		const reason = screen.getByRole("alert");
		expect(submit).toBeDisabled();
		expect(submit).toHaveAttribute("aria-disabled", "true");
		expect(reason).toHaveTextContent(
			"Fill in and fix the required fields before submitting.",
		);
		expect(reason).toBeVisible();
		expect(reason).toHaveAttribute("aria-live", "assertive");
		expect(submit).toHaveAttribute(
			"title",
			"Fill in and fix the required fields before submitting.",
		);

		const input = screen.getByRole("textbox");
		fireEvent.input(input, { target: { value: "https://example.com" } });

		expect(submit).not.toBeDisabled();
		expect(submit).toHaveAttribute("aria-disabled", "false");
		expect(reason).toBeEmptyDOMElement();
		expect(reason).not.toBeVisible();
		expect(submit).not.toHaveAttribute("title");
	});

	it("enforces require-one and require-one-exclusive rules", () => {
		render(
			<>
				<form
					data-require-one="job_id,video_url"
					data-require-one-exclusive="true"
				>
					<input name="job_id" />
					<input name="video_url" />
					<button type="submit">Load</button>
				</form>
				<FormValidationController />
			</>,
		);

		const submit = screen.getByRole("button", { name: "Load" });
		const [jobId, videoUrl] = screen.getAllByRole("textbox");
		const reason = screen.getByRole("alert");

		expect(submit).toBeDisabled();
		expect(reason).toHaveTextContent(
			"Fill in at least one required source before submitting.",
		);
		expect(reason).toBeVisible();
		expect(submit).toHaveAttribute(
			"title",
			"Fill in at least one required source before submitting.",
		);

		fireEvent.input(jobId, { target: { value: "job-1" } });
		expect(submit).not.toBeDisabled();
		expect(reason).toBeEmptyDOMElement();
		expect(reason).not.toBeVisible();
		expect(submit).not.toHaveAttribute("title");

		fireEvent.input(videoUrl, { target: { value: "https://example.com/v" } });
		expect(submit).toBeDisabled();
		expect(reason).toHaveTextContent(
			"Only one source can be filled right now. Clear the extra inputs before submitting.",
		);
		expect(reason).toBeVisible();
		expect(submit).toHaveAttribute(
			"title",
			"Only one source can be filled right now. Clear the extra inputs before submitting.",
		);

		fireEvent.input(videoUrl, { target: { value: "" } });
		expect(submit).not.toBeDisabled();
		expect(reason).toBeEmptyDOMElement();
		expect(reason).not.toBeVisible();
	});

	it("toggles dependent field based on checkbox state", () => {
		render(
			<>
				<form>
					<label>
						<input name="daily_digest_enabled" type="checkbox" />
						Enable
					</label>
					<input
						name="daily_digest_hour_utc"
						data-disabled-unless-checked="daily_digest_enabled"
					/>
					<button type="submit">Save</button>
				</form>
				<FormValidationController />
			</>,
		);

		const checkbox = screen.getByRole("checkbox");
		const input = screen.getByRole("textbox");

		expect(input).toBeDisabled();
		expect(input).toHaveAttribute("aria-disabled", "true");

		fireEvent.click(checkbox);

		expect(input).not.toBeDisabled();
		expect(input).toHaveAttribute("aria-disabled", "false");
	});

	it("toggles dependent field when checkbox state is mirrored through a hidden input", () => {
		render(
			<>
				<form>
					<input name="daily_digest_enabled" type="hidden" value="" />
					<input
						id="daily-digest-enabled"
						type="checkbox"
						aria-label="Enable daily digest"
						className="sr-only"
					/>
					<input
						name="daily_digest_hour_utc"
						data-disabled-unless-checked="daily_digest_enabled"
					/>
					<button type="submit">Save</button>
				</form>
				<FormValidationController />
			</>,
		);

		const hiddenInput = document.querySelector<HTMLInputElement>(
			'input[type="hidden"][name="daily_digest_enabled"]',
		);
		const input = screen.getByRole("textbox");

		expect(input).toBeDisabled();
		expect(input).toHaveAttribute("aria-disabled", "true");

		if (!hiddenInput) {
			throw new Error("daily_digest_enabled hidden input should exist");
		}
		hiddenInput.value = "on";
		fireEvent.input(hiddenInput);

		expect(input).not.toBeDisabled();
		expect(input).toHaveAttribute("aria-disabled", "false");
	});
});
