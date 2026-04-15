import {
	act,
	fireEvent,
	render,
	screen,
	waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SyncNowButton } from "@/components/sync-now-button";

const mockRefresh = vi.fn();
vi.mock("next/navigation", () => ({
	useRouter: () => ({ refresh: mockRefresh }),
}));

const mockPollIngest = vi.fn();
vi.mock("@/lib/api/client", () => ({
	apiClient: { pollIngest: (...args: unknown[]) => mockPollIngest(...args) },
}));

describe("SyncNowButton", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	afterEach(() => {
		vi.restoreAllMocks();
	});

	it("renders idle label", () => {
		render(<SyncNowButton />);
		expect(screen.getByRole("button", { name: "Refresh list" })).toHaveAttribute(
			"data-variant",
			"hero",
		);
	});

	it("shows loading state and prevents duplicate requests while in flight", async () => {
		let resolve!: () => void;
		mockPollIngest.mockReturnValue(
			new Promise<void>((r) => {
				resolve = r;
			}),
		);

		render(<SyncNowButton />);
		const button = screen.getByRole("button", { name: "Refresh list" });

		fireEvent.click(button);
		fireEvent.click(button);

		await waitFor(() =>
			expect(
				screen.getByRole("button", { name: "Refreshing…" }),
			).toBeInTheDocument(),
		);
		expect(screen.getByRole("button", { name: "Refreshing…" })).toBeDisabled();
		expect(mockPollIngest).toHaveBeenCalledTimes(1);
		expect(mockPollIngest).toHaveBeenCalledWith({});

		await act(async () => {
			resolve();
		});
	});

	it("shows success state then returns to idle and refreshes router", async () => {
		mockPollIngest.mockResolvedValue(undefined);
		render(<SyncNowButton />);

		await act(async () => {
			fireEvent.click(screen.getByRole("button", { name: "Refresh list" }));
		});

		await waitFor(() =>
			expect(
				screen.getByRole("button", { name: "List updated" }),
			).toBeInTheDocument(),
		);
		expect(mockPollIngest).toHaveBeenCalledTimes(1);

		await waitFor(
			() => {
				expect(
					screen.getByRole("button", { name: "Refresh list" }),
				).toBeInTheDocument();
				expect(mockRefresh).toHaveBeenCalled();
			},
			{
				timeout: 2500,
			},
		);
	});

	it("uses atomic status output and switches to assertive announcements on error", async () => {
		mockPollIngest.mockRejectedValue(new Error("Network error"));
		render(<SyncNowButton />);
		const status = document.getElementById("sync-now-status");

		expect(status).not.toBeNull();
		expect(status).toHaveAttribute("aria-atomic", "true");
		expect(status).toHaveAttribute("aria-live", "polite");

		await act(async () => {
			fireEvent.click(screen.getByRole("button", { name: "Refresh list" }));
		});

		await waitFor(() =>
			expect(
				screen.getByRole("button", { name: "Refresh failed, retry" }),
			).toBeInTheDocument(),
		);
		expect(status).toHaveAttribute("aria-live", "assertive");
		expect(
			screen.getByRole("button", { name: "Refresh failed, retry" }),
		).toHaveAttribute("data-variant", "destructive");
	});

	it("keeps error state until user retries and can recover on next success", async () => {
		mockPollIngest.mockRejectedValueOnce(new Error("Network error"));
		mockPollIngest.mockResolvedValueOnce(undefined);
		render(<SyncNowButton />);

		await act(async () => {
			fireEvent.click(screen.getByRole("button", { name: "Refresh list" }));
		});

		await waitFor(() =>
			expect(
				screen.getByRole("button", { name: "Refresh failed, retry" }),
			).toBeInTheDocument(),
		);
		expect(
			screen.getByRole("button", { name: "Refresh failed, retry" }),
		).toHaveAttribute("data-variant", "destructive");
		expect(
			screen.getByRole("button", { name: "Refresh failed, retry" }),
		).toHaveAttribute("data-feedback-state", "error");
		expect(mockPollIngest).toHaveBeenCalledTimes(1);
		expect(mockRefresh).not.toHaveBeenCalled();

		await waitFor(
			() => {
				expect(
					screen.getByRole("button", { name: "Refresh failed, retry" }),
				).toBeInTheDocument();
			},
			{
				timeout: 3500,
			},
		);

		await act(async () => {
			fireEvent.click(
				screen.getByRole("button", { name: "Refresh failed, retry" }),
			);
		});

		await waitFor(() =>
			expect(
				screen.getByRole("button", { name: "List updated" }),
			).toBeInTheDocument(),
		);
		await waitFor(
			() => {
				expect(
					screen.getByRole("button", { name: "Refresh list" }),
				).toBeInTheDocument();
				expect(mockRefresh).toHaveBeenCalledTimes(1);
			},
			{
				timeout: 2500,
			},
		);
	});

	it("applies button feedback states without relying on legacy status chips", async () => {
		let resolveFirstSync!: () => void;
		mockPollIngest.mockReturnValueOnce(
			new Promise<void>((resolve) => {
				resolveFirstSync = resolve;
			}),
		);
		mockPollIngest.mockRejectedValueOnce(new Error("Network error"));
		render(<SyncNowButton />);

		await act(async () => {
			fireEvent.click(screen.getByRole("button", { name: "Refresh list" }));
		});

		const loadingButton = await screen.findByRole("button", {
			name: "Refreshing…",
		});
		expect(loadingButton).toHaveAttribute("data-variant", "secondary");
		expect(loadingButton).toHaveAttribute("data-feedback-state", "loading");
		const loadingHint = document.querySelector(
			'[data-part="status-hint"][data-state="loading"]',
		);
		expect(loadingHint).not.toBeNull();
		expect(loadingHint).toHaveTextContent(
			"Pulling in the newest reading. Please wait.",
		);

		await act(async () => {
			resolveFirstSync();
		});

		const doneButton = await screen.findByRole("button", {
			name: "List updated",
		});
		expect(doneButton).toHaveAttribute("data-variant", "success");
		expect(doneButton).toHaveAttribute("data-feedback-state", "done");
		const doneHint = document.querySelector(
			'[data-part="status-hint"][data-state="done"]',
		);
		expect(doneHint).not.toBeNull();
		expect(doneHint).toHaveTextContent(
			"List updated. Refreshing the view next.",
		);
		expect(doneHint).not.toHaveClass("status-chip-feedback");

		const idleButton = await screen.findByRole(
			"button",
			{ name: "Refresh list" },
			{ timeout: 2500 },
		);
		expect(idleButton).toHaveAttribute("data-variant", "hero");

		await act(async () => {
			fireEvent.click(idleButton);
		});

		const errorButton = await screen.findByRole("button", {
			name: "Refresh failed, retry",
		});
		expect(errorButton).toHaveAttribute("data-variant", "destructive");
		expect(errorButton).toHaveAttribute("data-feedback-state", "error");
		expect(errorButton).toHaveAttribute(
			"title",
			"Refresh failed. Press Enter or Space to retry.",
		);
		const errorHint = document.querySelector(
			'[data-part="status-hint"][data-state="error"]',
		);
		expect(errorHint).not.toBeNull();
		expect(errorHint).toHaveTextContent(
			"Refresh failed. Check the network or API health, then retry.",
		);
		expect(errorHint).not.toHaveClass("status-chip-feedback");
	}, 8000);
});
