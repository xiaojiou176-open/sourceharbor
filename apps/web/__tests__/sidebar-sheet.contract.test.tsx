import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { usePathnameMock, useSearchParamsMock } = vi.hoisted(() => ({
	usePathnameMock: vi.fn(),
	useSearchParamsMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
	usePathname: usePathnameMock,
	useSearchParams: useSearchParamsMock,
}));

vi.mock("next/link", () => ({
	default: ({
		href,
		children,
		...rest
	}: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
		<a href={href} {...rest}>
			{children}
		</a>
	),
}));

vi.mock("@/components/theme-toggle", () => ({
	ThemeToggle: () => (
		<button type="button" data-slot="button">
			Switch theme
		</button>
	),
}));

import { Sidebar } from "@/components/sidebar";
import {
	Sheet,
	SheetContent,
	SheetDescription,
	SheetTitle,
	SheetTrigger,
} from "@/components/ui/sheet";

function createSearchParams(value: string): URLSearchParams {
	return new URLSearchParams(value);
}

function mockMatchMedia(matches: boolean) {
	Object.defineProperty(window, "matchMedia", {
		configurable: true,
		writable: true,
		value: vi.fn().mockImplementation(() => ({
			matches,
			media: "(max-width: 768px)",
			onchange: null,
			addEventListener: vi.fn(),
			removeEventListener: vi.fn(),
			addListener: vi.fn(),
			removeListener: vi.fn(),
			dispatchEvent: vi.fn(),
		})),
	});
}

function SidebarSheetHarness() {
	return (
		<Sheet>
			<SheetTrigger>Open navigation</SheetTrigger>
			<SheetContent side="left">
				<SheetTitle>Mobile navigation</SheetTitle>
				<SheetDescription>
					Sidebar drawer navigation for mobile.
				</SheetDescription>
				<Sidebar
					subscriptions={[
						{
							id: "sub-tech-1",
							platform: "youtube",
							source_type: "url",
							source_value: "https://youtube.com/@tech",
							source_name: "Tech Daily",
							support_tier: "generic_supported",
							content_profile: "article",
							adapter_type: "rss_generic",
							source_url: "https://example.com/feed.xml",
							rsshub_route: "",
							category: "tech",
							tags: [],
							priority: 50,
							enabled: true,
							created_at: "2026-03-01T00:00:00Z",
							updated_at: "2026-03-01T00:00:00Z",
						},
					]}
					apiHealthState="healthy"
					apiHealthUrl="http://127.0.0.1:9000/healthz"
					apiHealthLabel="Healthy"
				/>
			</SheetContent>
		</Sheet>
	);
}

describe("Sidebar + Sheet contract", () => {
	const SIDEBAR_TIMEOUT_MS = 15_000;

	beforeEach(() => {
		vi.clearAllMocks();
		usePathnameMock.mockReturnValue("/feed");
		useSearchParamsMock.mockReturnValue(
			createSearchParams("category=tech&sub=sub-tech-1"),
		);
		mockMatchMedia(false);
	});

	it(
		"keeps feed frontstage focused on reading and sources",
		() => {
			render(
				<Sidebar
					subscriptions={[
						{
							id: "sub-tech-1",
							platform: "youtube",
							source_type: "url",
							source_value: "https://youtube.com/@tech",
							source_name: "Tech Daily",
							support_tier: "generic_supported",
							content_profile: "article",
							adapter_type: "rss_generic",
							source_url: "https://example.com/feed.xml",
							rsshub_route: "",
							category: "tech",
							tags: [],
							priority: 50,
							enabled: true,
							created_at: "2026-03-01T00:00:00Z",
							updated_at: "2026-03-01T00:00:00Z",
						},
						{
							id: "sub-disabled",
							platform: "bilibili",
							source_type: "url",
							source_value: "https://bilibili.com/disabled",
							source_name: "Disabled Source",
							support_tier: "generic_supported",
							content_profile: "article",
							adapter_type: "rss_generic",
							source_url: "https://example.com/disabled.xml",
							rsshub_route: "",
							category: "creator",
							tags: [],
							priority: 50,
							enabled: false,
							created_at: "2026-03-01T00:00:00Z",
							updated_at: "2026-03-01T00:00:00Z",
						},
					]}
					apiHealthState="healthy"
					apiHealthUrl="http://127.0.0.1:9000/healthz"
					apiHealthLabel="Healthy"
				/>,
			);

			expect(
				screen.getByRole("complementary", { name: "Sidebar navigation" }),
			).toBeInTheDocument();
			expect(screen.getByRole("link", { name: "Sources" })).toHaveAttribute(
				"href",
				"/subscriptions",
			);
			expect(
				screen.queryByRole("link", { name: "System status" }),
			).not.toBeInTheDocument();
			expect(
				screen.queryByRole("link", { name: "Saved topics" }),
			).not.toBeInTheDocument();
			expect(
				screen.queryByRole("link", { name: "What changed" }),
			).not.toBeInTheDocument();
			expect(
				screen.queryByRole("link", { name: "Story briefs" }),
			).not.toBeInTheDocument();
			expect(
				screen.queryByRole("link", { name: "Search" }),
			).not.toBeInTheDocument();
			expect(
				screen.queryByRole("link", { name: "Ask" }),
			).not.toBeInTheDocument();
			expect(
				screen.queryByRole("link", { name: "Tech" }),
			).not.toBeInTheDocument();
			expect(
				screen.queryByRole("link", { name: "Tech Daily" }),
			).not.toBeInTheDocument();
			expect(
				screen.queryByRole("link", { name: "Disabled Source" }),
			).toBeNull();
			expect(
				screen.queryByRole("link", { name: /API health/i }),
			).not.toBeInTheDocument();
		},
		SIDEBAR_TIMEOUT_MS,
	);

	it(
		"opens sidebar content inside sheet container",
		() => {
			render(<SidebarSheetHarness />);

			fireEvent.click(screen.getByRole("button", { name: "Open navigation" }));

			expect(screen.getByRole("dialog")).toBeInTheDocument();
			expect(
				screen.getByRole("heading", { name: "Mobile navigation" }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("complementary", { name: "Sidebar navigation" }),
			).toBeInTheDocument();
		},
		SIDEBAR_TIMEOUT_MS,
	);

	it(
		"wires the real mobile sheet trigger in Sidebar when viewport is collapsed",
		() => {
			mockMatchMedia(true);
			render(
				<Sidebar
					subscriptions={[]}
					apiHealthState="healthy"
					apiHealthUrl="http://127.0.0.1:9000/healthz"
					apiHealthLabel="Healthy"
				/>,
			);

			fireEvent.click(
				screen.getByRole("button", { name: "Open navigation panel" }),
			);

			expect(screen.getByRole("dialog")).toBeInTheDocument();
			expect(
				screen.getByRole("complementary", { name: "Sidebar navigation" }),
			).toBeInTheDocument();
		},
		SIDEBAR_TIMEOUT_MS,
	);

	it(
		"falls back safely when matchMedia is unavailable and supports manual collapse toggle",
		() => {
			Object.defineProperty(window, "matchMedia", {
				configurable: true,
				writable: true,
				value: undefined,
			});
			render(
				<Sidebar
					subscriptions={[]}
					apiHealthState="healthy"
					apiHealthUrl="http://127.0.0.1:9000/healthz"
					apiHealthLabel="Healthy"
				/>,
			);

			const toggle = screen.getByRole("button", { name: "Collapse sidebar" });
			fireEvent.click(toggle);
			expect(
				screen.getByRole("button", { name: "Open navigation panel" }),
			).toBeInTheDocument();
		},
		SIDEBAR_TIMEOUT_MS,
	);

	it(
		"marks homepage active and skips category grouping when no enabled subscriptions exist",
		() => {
			usePathnameMock.mockReturnValue("/");
			useSearchParamsMock.mockReturnValue(createSearchParams(""));

			render(
				<Sidebar
					subscriptions={[
						{
							id: "sub-disabled-only",
							platform: "rss",
							source_type: "rss_generic",
							source_value: "",
							source_name: "",
							support_tier: "generic_supported",
							content_profile: "article",
							adapter_type: "rss_generic",
							source_url: null,
							rsshub_route: "",
							category: "misc",
							tags: [],
							priority: 10,
							enabled: false,
							created_at: "2026-03-01T00:00:00Z",
							updated_at: "2026-03-01T00:00:00Z",
						},
					]}
					apiHealthState="healthy"
					apiHealthUrl="http://127.0.0.1:9000/healthz"
					apiHealthLabel="Healthy"
				/>,
			);

			expect(screen.getByRole("link", { name: "Home" })).toHaveAttribute(
				"aria-current",
				"page",
			);
			expect(screen.queryByRole("link", { name: "Tech" })).toBeNull();
			expect(
				screen.queryByRole("link", { name: "Reading desk" }),
			).not.toHaveAttribute("aria-current");
		},
		SIDEBAR_TIMEOUT_MS,
	);

	it(
		"keeps subscription load failure hint out of feed frontstage",
		() => {
			render(
				<Sidebar
					subscriptions={[]}
					subscriptionsLoadError
					apiHealthState="unhealthy"
					apiHealthUrl="http://127.0.0.1:9000/healthz"
					apiHealthLabel="Unhealthy"
				/>,
			);

			expect(
				screen.queryByText(
					/Could not load your followed sources\. Retry from Following\./i,
				),
			).not.toBeInTheDocument();
		},
		SIDEBAR_TIMEOUT_MS,
	);

	it(
		"keeps followed source tree out of feed frontstage even when a specific source is selected",
		() => {
			usePathnameMock.mockReturnValue("/feed");
			useSearchParamsMock.mockReturnValue(
				createSearchParams("sub=sub-fallback"),
			);

			render(
				<Sidebar
					subscriptions={[
						{
							id: "sub-fallback",
							platform: "youtube",
							source_type: "url",
							source_value: "https://example.com/source",
							source_name: "",
							support_tier: "generic_supported",
							content_profile: "article",
							adapter_type: "rss_generic",
							source_url: null,
							rsshub_route: "",
							category: "tech",
							tags: [],
							priority: 40,
							enabled: true,
							created_at: "2026-03-01T00:00:00Z",
							updated_at: "2026-03-01T00:00:00Z",
						},
						{
							id: "sub-unnamed",
							platform: "youtube",
							source_type: "url",
							source_value: "",
							source_name: "",
							support_tier: "generic_supported",
							content_profile: "article",
							adapter_type: "rss_generic",
							source_url: null,
							rsshub_route: "",
							category: "tech",
							tags: [],
							priority: 30,
							enabled: true,
							created_at: "2026-03-01T00:00:00Z",
							updated_at: "2026-03-01T00:00:00Z",
						},
					]}
					apiHealthState="timeout_or_unknown"
					apiHealthUrl="http://127.0.0.1:9000/healthz"
					apiHealthLabel="Timeout / Unknown"
				/>,
			);

			expect(
				screen.queryByRole("link", { name: "https://example.com/source" }),
			).not.toBeInTheDocument();
			expect(
				screen.queryByRole("link", { name: "Untitled" }),
			).not.toBeInTheDocument();
			expect(
				screen.queryByRole("link", { name: /API health/i }),
			).not.toBeInTheDocument();
		},
		SIDEBAR_TIMEOUT_MS,
	);

	it(
		"marks jobs and settings routes active while feed root stays inactive",
		() => {
			usePathnameMock.mockReturnValue("/jobs/details");
			useSearchParamsMock.mockReturnValue(createSearchParams(""));

			const { rerender } = render(
				<Sidebar
					subscriptions={[]}
					apiHealthState="healthy"
					apiHealthUrl="http://127.0.0.1:9000/healthz"
					apiHealthLabel="Healthy"
				/>,
			);

			expect(
				screen.getByRole("link", { name: "Processing history" }),
			).toHaveAttribute("aria-current", "page");
			expect(
				screen.getByRole("link", { name: "Reading desk" }),
			).not.toHaveAttribute("aria-current");

			usePathnameMock.mockReturnValue("/settings/profile");
			rerender(
				<Sidebar
					subscriptions={[]}
					apiHealthState="healthy"
					apiHealthUrl="http://127.0.0.1:9000/healthz"
					apiHealthLabel="Healthy"
				/>,
			);

			expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute(
				"aria-current",
				"page",
			);
		},
		SIDEBAR_TIMEOUT_MS,
	);

	it(
		"shows Search and Ask in primary navigation and marks Search active on search routes",
		() => {
			usePathnameMock.mockReturnValue("/search");
			useSearchParamsMock.mockReturnValue(createSearchParams(""));

			render(
				<Sidebar
					subscriptions={[]}
					apiHealthState="healthy"
					apiHealthUrl="http://127.0.0.1:9000/healthz"
					apiHealthLabel="Healthy"
				/>,
			);

			expect(screen.getByRole("link", { name: "Search" })).toHaveAttribute(
				"aria-current",
				"page",
			);
			expect(screen.getByRole("link", { name: "Ask" })).toHaveAttribute(
				"href",
				"/ask",
			);
		},
		SIDEBAR_TIMEOUT_MS,
	);

	it(
		"keeps feed root active without exposing system health on the frontstage",
		() => {
			usePathnameMock.mockReturnValue("/feed");
			useSearchParamsMock.mockReturnValue(createSearchParams(""));

			render(
				<Sidebar
					subscriptions={[]}
					apiHealthState="unhealthy"
					apiHealthUrl="http://127.0.0.1:9000/healthz"
					apiHealthLabel="Unhealthy"
				/>,
			);

			expect(
				screen.getByRole("link", { name: "Reading desk" }),
			).toHaveAttribute("aria-current", "page");
			expect(
				screen.queryByRole("link", { name: /API health/i }),
			).not.toBeInTheDocument();
		},
		SIDEBAR_TIMEOUT_MS,
	);
});
