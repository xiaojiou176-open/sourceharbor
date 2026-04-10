import { render, screen } from "@testing-library/react";
import type { JSX } from "react";
import { describe, expect, it } from "vitest";

import FeedLoading from "@/app/feed/loading";
import JobsLoading from "@/app/jobs/loading";
import AppLoading from "@/app/loading";
import SettingsLoading from "@/app/settings/loading";
import SubscriptionsLoading from "@/app/subscriptions/loading";

type LoadingCase = {
	name: string;
	Component: () => JSX.Element;
	heading: string;
	message: string;
	describedBy: string;
	hasSrOnlyPageHeading?: boolean;
};

const LOADING_CASES: LoadingCase[] = [
	{
		name: "dashboard loading",
		Component: AppLoading,
		heading: "Dashboard loading",
		message: "Loading the command center. Please wait.",
		describedBy: "app-loading-message",
		hasSrOnlyPageHeading: true,
	},
	{
		name: "jobs loading",
		Component: JobsLoading,
		heading: "Job trace loading",
		message: "Loading job details. Please wait.",
		describedBy: "jobs-loading-message",
	},
	{
		name: "settings loading",
		Component: SettingsLoading,
		heading: "Settings loading",
		message: "Loading notification settings. Please wait.",
		describedBy: "settings-loading-message",
	},
	{
		name: "subscriptions loading",
		Component: SubscriptionsLoading,
		heading: "Loading subscriptions",
		message: "Loading subscription data. Please wait.",
		describedBy: "subscriptions-loading-message",
	},
	{
		name: "feed loading",
		Component: FeedLoading,
		heading: "Digest feed loading",
		message: "Loading the digest feed. Please wait.",
		describedBy: "feed-loading-message",
	},
];

describe("app loading surfaces", () => {
	it.each(
		LOADING_CASES,
	)("renders $name with accessible busy/status semantics", ({
		Component,
		heading,
		message,
		describedBy,
		hasSrOnlyPageHeading = false,
	}) => {
		const { container, unmount } = render(<Component />);

		const section = container.querySelector("section");
		expect(section).not.toBeNull();
		expect(section).toHaveAttribute("aria-busy", "true");
		expect(section).toHaveAttribute("aria-describedby", describedBy);

		const headingNode = screen.getByText(heading, {
			selector: '[data-slot="card-title"]',
		});
		expect(headingNode).toHaveAttribute("aria-hidden", "true");
		expect(container.querySelectorAll(".skeleton-line")).toHaveLength(3);
		const pageHeading = screen.queryByRole("heading", {
			level: 1,
			name: heading,
		});
		expect(Boolean(pageHeading)).toBe(hasSrOnlyPageHeading);
		expect(pageHeading?.classList.contains("sr-only") ?? false).toBe(
			hasSrOnlyPageHeading,
		);

		const status = screen.getByRole("status");
		expect(status).toHaveAttribute("id", describedBy);
		expect(status).toHaveAttribute("aria-live", "polite");
		expect(status).toHaveAttribute("aria-atomic", "true");
		expect(status).toHaveTextContent(message);

		unmount();
	});
});
