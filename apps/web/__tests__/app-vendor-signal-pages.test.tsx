import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import BriefingsPage from "@/app/briefings/page";
import SubscriptionsPage from "@/app/subscriptions/page";
import WatchlistsPage from "@/app/watchlists/page";

const mockListSubscriptions = vi.fn();
const mockListSubscriptionTemplates = vi.fn();
const mockListVendorSignalTemplates = vi.fn();
const mockListWatchlists = vi.fn();
const mockGetOpsInbox = vi.fn();
const mockGetWatchlistTrend = vi.fn();
const mockGetWatchlistBriefingPage = vi.fn();

vi.mock("next/link", () => ({
	default: ({
		href,
		children,
		...rest
	}: {
		href: string;
		children: ReactNode;
	}) => (
		<a href={href} {...rest}>
			{children}
		</a>
	),
}));

vi.mock("@/app/action-security", () => ({
	getActionSessionTokenForForm: () => "test-session-token",
}));

vi.mock("@/components/subscription-batch-panel", () => ({
	SubscriptionBatchPanel: () => <div data-testid="subscription-batch-panel" />,
}));

vi.mock("@/lib/api/client", () => ({
	apiClient: {
		listSubscriptions: (...args: unknown[]) => mockListSubscriptions(...args),
		listSubscriptionTemplates: (...args: unknown[]) =>
			mockListSubscriptionTemplates(...args),
		listVendorSignalTemplates: (...args: unknown[]) =>
			mockListVendorSignalTemplates(...args),
		listWatchlists: (...args: unknown[]) => mockListWatchlists(...args),
		getOpsInbox: (...args: unknown[]) => mockGetOpsInbox(...args),
		getWatchlistTrend: (...args: unknown[]) => mockGetWatchlistTrend(...args),
		getWatchlistBriefingPage: (...args: unknown[]) =>
			mockGetWatchlistBriefingPage(...args),
	},
}));

describe("vendor signal surfaces", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		mockListSubscriptions.mockResolvedValue([]);
		mockListSubscriptionTemplates.mockResolvedValue({
			support_tiers: [
				{
					id: "strong_supported",
					label: "Strong support",
					description: "Strong support lane.",
					content_profile: "video",
					supports_video_pipeline: true,
					verification_status: "verified",
				},
				{
					id: "generic_supported",
					label: "Generic support",
					description: "Generic support lane.",
					content_profile: "article",
					supports_video_pipeline: false,
					verification_status: "substrate",
				},
			],
			templates: [],
		});
		mockListVendorSignalTemplates.mockResolvedValue({
			signal_layers: [
				{
					id: "confirmed",
					label: "Confirmed truth",
					description: "Official docs, changelog, status, and blog updates.",
				},
				{
					id: "observation",
					label: "Observation layer",
					description: "Fast signals that need confirmation first.",
				},
			],
			vendors: [
				{
					id: "openai",
					label: "OpenAI",
					description: "Track official product and API changes.",
					official_first_move:
						"Start with the API changelog and status before you repeat a claim.",
					x_policy_summary:
						"Treat OpenAI on X as a fast signal only until docs or status confirms it.",
					confirmation_chain: [
						{
							id: "fast-signal",
							label: "Fast signal",
							description: "Treat X posts as observation only.",
						},
						{
							id: "confirm",
							label: "Confirm",
							description:
								"Promote only after changelog, status, or blog corroborates it.",
						},
					],
					starter_watchlist: {
						name: "OpenAI signals",
						matcher_type: "source_match",
						matcher_value: "openai",
						delivery_channel: "dashboard",
						briefing_goal: "What changed across official OpenAI channels this week?",
					},
					channels: [
						{
							id: "openai-api-changelog",
							label: "API changelog",
							url: "https://developers.openai.com/api/docs/changelog",
							channel_kind: "changelog",
							signal_layer: "confirmed",
							why_it_matters: "Contract truth for model and API changes.",
							ingest_mode: "manual_url",
						},
						{
							id: "openai-x",
							label: "OpenAI on X",
							url: "https://x.com/OpenAI",
							channel_kind: "x_account",
							signal_layer: "observation",
							why_it_matters: "Fast hints and screenshots, not final truth.",
							ingest_mode: "link_only",
						},
					],
				},
			],
		});
		mockListWatchlists.mockResolvedValue([]);
		mockGetOpsInbox.mockResolvedValue({ gates: { notifications: null } });
		mockGetWatchlistTrend.mockResolvedValue(null);
		mockGetWatchlistBriefingPage.mockResolvedValue(null);
	});

	it("renders vendor sources on subscriptions with confirmed vs observation guidance", async () => {
		render(await SubscriptionsPage({ searchParams: {} }));

		expect(
			screen.getByRole("heading", { name: "Vendor sources" }),
		).toBeInTheDocument();
		expect(screen.getByText("OpenAI")).toBeInTheDocument();
		expect(screen.getAllByText("Confirmed truth").length).toBeGreaterThan(0);
		expect(screen.getAllByText("Observation layer").length).toBeGreaterThan(0);
		expect(
			screen.getByRole("link", { name: "Paste first confirmed source" }),
		).toHaveAttribute("href", expect.stringContaining("/subscriptions?raw_input="));
		expect(
			screen.getByRole("link", { name: "Create vendor watchlist" }),
		).toHaveAttribute("href", expect.stringContaining("/watchlists?compose=1"));
	});

	it("renders vendor starters on watchlists with a briefing goal", async () => {
		render(await WatchlistsPage({ searchParams: {} }));

		expect(
			screen.getByRole("heading", { name: "Vendor starters" }),
		).toBeInTheDocument();
		expect(
			screen.getByText(/What changed across official OpenAI channels this week/i),
		).toBeInTheDocument();
		expect(
			screen.getByRole("link", { name: "Create starter watchlist" }),
		).toHaveAttribute("href", expect.stringContaining("matcher_type=source_match"));
	});

	it("opens the create form when vendor starter params prefill a watchlist", async () => {
		render(
			await WatchlistsPage({
				searchParams: {
					compose: "1",
					name: "OpenAI signals",
					matcher_type: "source_match",
					matcher_value: "openai",
					delivery_channel: "dashboard",
				},
			}),
		);

		expect(
			screen.getByText("Continue with OpenAI"),
		).toBeInTheDocument();
		expect(screen.getByDisplayValue("OpenAI signals")).toBeInTheDocument();
		expect(screen.getByDisplayValue("openai")).toBeInTheDocument();
	});

	it("points empty briefings back to vendor sources and watchlists", async () => {
		render(await BriefingsPage({ searchParams: {} }));

		expect(screen.getByText(/Start with vendor sources first/i)).toBeInTheDocument();
		expect(screen.getByText("Current summary")).toBeInTheDocument();
		expect(screen.getByText("Recent changes")).toBeInTheDocument();
		expect(screen.getByText("Evidence nearby")).toBeInTheDocument();
		const links = screen.getAllByRole("link");
		const subscriptionsLink = links.find((link) =>
			link.getAttribute("href")?.startsWith("/subscriptions#vendor-sources"),
		);
		const watchlistsLink = links.find((link) =>
			link.getAttribute("href")?.startsWith("/watchlists?compose=1"),
		);
		expect(subscriptionsLink?.getAttribute("href")).toBe(
			"/subscriptions#vendor-sources",
		);
		expect(watchlistsLink?.getAttribute("href")).toBe(
			"/watchlists?compose=1#create-watchlist",
		);
	});
});
