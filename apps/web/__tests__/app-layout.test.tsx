import { screen } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import RootLayout from "@/app/layout";

vi.mock("geist/font/sans", () => ({
	GeistSans: { variable: "font-geist-sans" },
}));
vi.mock("geist/font/mono", () => ({
	GeistMono: { variable: "font-geist-mono" },
}));

vi.mock("next/link", () => ({
	default: ({
		href,
		children,
		...rest
	}: {
		href: string;
		children: React.ReactNode;
	}) => (
		<a href={href} {...rest}>
			{children}
		</a>
	),
}));

vi.mock("@/components/theme-provider", () => ({
	ThemeProvider: ({ children }: { children: React.ReactNode }) => (
		<>{children}</>
	),
}));

vi.mock("@/components/sidebar-wrapper", () => ({
	SidebarWrapper: ({
		apiHealthState,
		apiHealthUrl,
		apiHealthLabel,
	}: {
		apiHealthState: string;
		apiHealthUrl: string;
		apiHealthLabel: string;
	}) => (
		<aside data-testid="sidebar-stub" aria-live="polite">
			sidebar
			<a href={apiHealthUrl} className={`api-health-dot-${apiHealthState}`}>
				API health: {apiHealthLabel}
			</a>
		</aside>
	),
}));

vi.mock("@/components/form-validation-controller", () => ({
	FormValidationController: () => (
		<div data-testid="form-validation-controller-stub" />
	),
}));

const fetchApiHealthStateMock = vi.fn();

vi.mock("@/lib/api/health", () => ({
	fetchApiHealthState: (options: unknown) => fetchApiHealthStateMock(options),
}));

describe("RootLayout", () => {
	it("shows healthy api state chip", async () => {
		process.env.API_PORT = "18000";
		fetchApiHealthStateMock.mockResolvedValue("healthy");

		const html = renderToStaticMarkup(
			await RootLayout({ children: <div>content</div> }),
		);

		expect(html).toContain("API health: Healthy");
		expect(html).toContain("http://127.0.0.1:18000/healthz");
		expect(fetchApiHealthStateMock).toHaveBeenCalledWith({ timeoutMs: 2000 });
	});

	it("shows unhealthy api state chip", async () => {
		fetchApiHealthStateMock.mockResolvedValue("unhealthy");

		const html = renderToStaticMarkup(
			await RootLayout({ children: <div>content</div> }),
		);

		expect(html).toContain("API health: Unhealthy");
	});

	it("shows timeout/unknown api state chip when fetch throws", async () => {
		fetchApiHealthStateMock.mockResolvedValue("timeout_or_unknown");

		const html = renderToStaticMarkup(
			await RootLayout({ children: <div>content</div> }),
		);

		expect(html).toContain("api-health-dot-timeout_or_unknown");
		expect(html).toContain("API health: Timeout / Unknown");
		expect(html).toContain('aria-live="polite"');
		expect(html).toContain("Skip to main content");
		expect(html).toContain('id="main-content"');
		expect(html).toContain("pl-14");
		expect(html).toContain(
			"pointer-events-none fixed left-2.5 top-2.5 z-40 md:hidden",
		);
		expect(html).toContain(
			"hidden w-[72px] shrink-0 border-r border-border/40 bg-background md:flex",
		);
		expect(html).toContain('tabindex="-1"');
	});

	it("renders skip link with accessible name", async () => {
		vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));

		document.body.innerHTML = renderToStaticMarkup(
			await RootLayout({ children: <div>content</div> }),
		);
		expect(
			screen.getByRole("link", { name: "Skip to main content" }),
		).toHaveAttribute("href", "#main-content");
	});
});
