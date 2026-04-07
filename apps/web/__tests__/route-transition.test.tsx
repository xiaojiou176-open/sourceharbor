import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { usePathnameMock } = vi.hoisted(() => ({
	usePathnameMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
	usePathname: usePathnameMock,
}));

import { RouteTransition } from "@/components/route-transition";

describe("RouteTransition", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.spyOn(window, "requestAnimationFrame").mockImplementation(
			(callback: FrameRequestCallback) => {
				callback(16);
				return 1;
			},
		);
		vi.spyOn(window, "cancelAnimationFrame").mockImplementation(() => {});
	});

	it("announces mapped route label and focuses the route heading", () => {
		usePathnameMock.mockReturnValue("/settings/profile");
		render(
			<RouteTransition>
				<div>
					<h2>旧标题</h2>
					<h1 data-route-heading>通知配置</h1>
				</div>
			</RouteTransition>,
		);

		const heading = screen.getByRole("heading", { name: "通知配置" });
		expect(screen.getByRole("status")).toHaveTextContent(
			"Switched to: Settings",
		);
		expect(heading).toHaveAttribute("tabindex", "-1");
		expect(document.activeElement).toBe(heading);
		// data-route-focus-target 已改为 useRef 追踪，不再写入 DOM 属性
		expect(heading).not.toHaveAttribute("data-route-focus-target");
	});

	it("maps root pathname to homepage label", () => {
		usePathnameMock.mockReturnValue("/");
		render(
			<RouteTransition>
				<h1>首页看板</h1>
			</RouteTransition>,
		);

		expect(screen.getByRole("status")).toHaveTextContent("Switched to: Home");
	});

	it("falls back to generic label for unknown routes", () => {
		usePathnameMock.mockReturnValue("/custom-route");
		render(
			<RouteTransition>
				<h1>自定义页面</h1>
			</RouteTransition>,
		);

		expect(screen.getByRole("status")).toHaveTextContent("Switched to: Page");
	});

	it("maps search route to the front-door label", () => {
		usePathnameMock.mockReturnValue("/search");
		render(
			<RouteTransition>
				<h1 data-route-heading>搜索入口</h1>
			</RouteTransition>,
		);

		expect(screen.getByRole("status")).toHaveTextContent("Switched to: Search");
	});

	it("maps ask route to the dedicated label", () => {
		usePathnameMock.mockReturnValue("/ask");
		render(
			<RouteTransition>
				<h1 data-route-heading>提问入口</h1>
			</RouteTransition>,
		);

		expect(screen.getByRole("status")).toHaveTextContent("Switched to: Ask");
	});

	it("maps ops route to the dedicated label", () => {
		usePathnameMock.mockReturnValue("/ops");
		render(
			<RouteTransition>
				<h1 data-route-heading>Ops inbox</h1>
			</RouteTransition>,
		);

		expect(screen.getByRole("status")).toHaveTextContent(
			"Switched to: Ops inbox",
		);
	});

	it("maps watchlists route to the dedicated label", () => {
		usePathnameMock.mockReturnValue("/watchlists");
		render(
			<RouteTransition>
				<h1 data-route-heading>追踪清单</h1>
			</RouteTransition>,
		);

		expect(screen.getByRole("status")).toHaveTextContent(
			"Switched to: Watchlists",
		);
	});

	it("maps trends route to the dedicated label", () => {
		usePathnameMock.mockReturnValue("/trends");
		render(
			<RouteTransition>
				<h1 data-route-heading>连续变化</h1>
			</RouteTransition>,
		);

		expect(screen.getByRole("status")).toHaveTextContent("Switched to: Trends");
	});

	it("maps briefings route to the dedicated label", () => {
		usePathnameMock.mockReturnValue("/briefings");
		render(
			<RouteTransition>
				<h1 data-route-heading>统一简报</h1>
			</RouteTransition>,
		);

		expect(screen.getByRole("status")).toHaveTextContent(
			"Switched to: Briefings",
		);
	});

	it("maps proof route to the dedicated label", () => {
		usePathnameMock.mockReturnValue("/proof");
		render(
			<RouteTransition>
				<h1 data-route-heading>证明边界</h1>
			</RouteTransition>,
		);

		expect(screen.getByRole("status")).toHaveTextContent("Switched to: Proof");
	});

	it("maps nested ingest runs routes to the dedicated label", () => {
		usePathnameMock.mockReturnValue("/ingest-runs/run-1");
		render(
			<RouteTransition>
				<h1 data-route-heading>摄取运行详情</h1>
			</RouteTransition>,
		);

		expect(screen.getByRole("status")).toHaveTextContent(
			"Switched to: Ingest runs",
		);
	});

	it("skips focus updates when no heading is present", () => {
		usePathnameMock.mockReturnValue("/feed");
		render(
			<RouteTransition>
				<div>无标题内容</div>
			</RouteTransition>,
		);

		expect(screen.getByRole("status")).toHaveTextContent(
			"Switched to: Digest feed",
		);
	});

	it("maps use-case routes to the dedicated label", () => {
		usePathnameMock.mockReturnValue("/use-cases/codex");
		render(
			<RouteTransition>
				<h1 data-route-heading>Codex operator workflow</h1>
			</RouteTransition>,
		);

		expect(screen.getByRole("status")).toHaveTextContent(
			"Switched to: Use cases",
		);
	});

	it("falls back to h2 when no explicit route heading or h1 exists", () => {
		usePathnameMock.mockReturnValue("/jobs/history");
		render(
			<RouteTransition>
				<section>
					<p>描述</p>
					<h2>历史任务</h2>
				</section>
			</RouteTransition>,
		);

		const heading = screen.getByRole("heading", { name: "历史任务" });
		expect(screen.getByRole("status")).toHaveTextContent("Switched to: Jobs");
		expect(heading).toHaveAttribute("tabindex", "-1");
		expect(document.activeElement).toBe(heading);
	});

	it("maps top-level ingest runs route to the dedicated label", () => {
		usePathnameMock.mockReturnValue("/ingest-runs");
		render(
			<RouteTransition>
				<h1 data-route-heading>摄取运行</h1>
			</RouteTransition>,
		);

		expect(screen.getByRole("status")).toHaveTextContent(
			"Switched to: Ingest runs",
		);
	});

	it("removes tabindex from previously focused heading when route updates", () => {
		let pathname = "/feed";
		usePathnameMock.mockImplementation(() => pathname);

		const { rerender } = render(
			<RouteTransition>
				<h1 data-route-heading>摘要页</h1>
			</RouteTransition>,
		);

		const firstHeading = screen.getByRole("heading", { name: "摘要页" });
		expect(firstHeading).toHaveAttribute("tabindex", "-1");

		pathname = "/jobs";
		rerender(
			<RouteTransition>
				<h1 data-route-heading>任务页</h1>
			</RouteTransition>,
		);

		const secondHeading = screen.getByRole("heading", { name: "任务页" });
		expect(secondHeading).toHaveAttribute("tabindex", "-1");
		expect(firstHeading).not.toHaveAttribute("tabindex");
	});

	it("cleans tabindex when unmounting", () => {
		usePathnameMock.mockReturnValue("/settings");
		const { unmount } = render(
			<RouteTransition>
				<h1 data-route-heading>设置页</h1>
			</RouteTransition>,
		);
		const heading = screen.getByRole("heading", { name: "设置页" });
		expect(heading).toHaveAttribute("tabindex", "-1");

		unmount();
		expect(heading).not.toHaveAttribute("tabindex");
	});

	it("keeps tabindex when the focused heading instance does not change", () => {
		usePathnameMock.mockReturnValue("/feed");
		const { rerender } = render(
			<RouteTransition>
				<h1 data-route-heading>同一标题</h1>
			</RouteTransition>,
		);

		const heading = screen.getByRole("heading", { name: "同一标题" });
		expect(heading).toHaveAttribute("tabindex", "-1");

		rerender(
			<RouteTransition>
				<h1 data-route-heading>同一标题</h1>
			</RouteTransition>,
		);

		expect(heading).toHaveAttribute("tabindex", "-1");
	});
});
