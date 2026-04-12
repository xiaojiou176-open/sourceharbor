import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ActionLink } from "@/components/action-link";
import { ErrorStateCard } from "@/components/error-state-card";
import { MetricCard } from "@/components/metric-card";
import { SidebarWrapper } from "@/components/sidebar-wrapper";
import { ThemeProvider } from "@/components/theme-provider";
import { ThemeToggle } from "@/components/theme-toggle";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuCheckboxItem,
	DropdownMenuContent,
	DropdownMenuGroup,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuPortal,
	DropdownMenuRadioGroup,
	DropdownMenuRadioItem,
	DropdownMenuSeparator,
	DropdownMenuShortcut,
	DropdownMenuSub,
	DropdownMenuSubContent,
	DropdownMenuSubTrigger,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectLabel,
	SelectSeparator,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";

const mockListSubscriptions = vi.fn();
const mockSetTheme = vi.fn();

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

vi.mock("@/lib/api/client", () => ({
	apiClient: {
		listSubscriptions: (...args: unknown[]) => mockListSubscriptions(...args),
	},
}));

vi.mock("@/components/sidebar", () => ({
	Sidebar: ({
		subscriptions,
		subscriptionsLoadError,
		apiHealthState,
		apiHealthUrl,
		apiHealthLabel,
	}: {
		subscriptions: Array<{ id: string }>;
		subscriptionsLoadError?: boolean;
		apiHealthState: string;
		apiHealthUrl: string;
		apiHealthLabel: string;
	}) => (
		<div data-testid="sidebar-proxy">
			<span>{subscriptions.length}</span>
			<span>{subscriptionsLoadError ? "load-error" : "load-ok"}</span>
			<span>{apiHealthState}</span>
			<span>{apiHealthUrl}</span>
			<span>{apiHealthLabel}</span>
		</div>
	),
}));

vi.mock("next-themes", () => ({
	ThemeProvider: ({ children, ...props }: { children: React.ReactNode }) => (
		<div data-testid="next-themes-provider" data-props={JSON.stringify(props)}>
			{children}
		</div>
	),
	useTheme: () => ({ setTheme: mockSetTheme }),
}));

describe("ui primitive coverage", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		Object.defineProperty(HTMLElement.prototype, "hasPointerCapture", {
			configurable: true,
			value: () => false,
		});
		Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
			configurable: true,
			value: () => undefined,
		});
	});

	it("renders ActionLink through shadcn Button asChild", () => {
		render(
			<ActionLink
				href="/feed"
				variant="outline"
				size="lg"
				aria-label="前往摘要"
			>
				打开摘要
			</ActionLink>,
		);

		const link = screen.getByRole("link", { name: "前往摘要" });
		expect(link).toHaveAttribute("href", "/feed");
		expect(link).toHaveAttribute("data-slot", "button");
		expect(link).toHaveAttribute("data-variant", "outline");
		expect(link).toHaveAttribute("data-size", "lg");
	});

	it("covers semantic button variants used by feed and sync actions", () => {
		render(
			<div>
				<Button variant="hero">主 CTA</Button>
				<Button variant="surface">次级操作</Button>
				<Button variant="success">成功反馈</Button>
			</div>,
		);

		expect(screen.getByRole("button", { name: "主 CTA" })).toHaveAttribute(
			"data-variant",
			"hero",
		);
		expect(screen.getByRole("button", { name: "次级操作" })).toHaveAttribute(
			"data-variant",
			"surface",
		);
		expect(screen.getByRole("button", { name: "成功反馈" })).toHaveAttribute(
			"data-variant",
			"success",
		);
	});

	it("renders Badge via asChild to cover slot branch", () => {
		render(
			<Badge asChild variant="link">
				<a href="/docs">查看文档</a>
			</Badge>,
		);

		const link = screen.getByRole("link", { name: "查看文档" });
		expect(link).toHaveAttribute("href", "/docs");
		expect(link).toHaveAttribute("data-slot", "badge");
		expect(link).toHaveAttribute("data-variant", "link");
	});

	it("renders MetricCard with accent, description and CTA", () => {
		render(
			<MetricCard
				label="失败任务"
				value="7"
				description="最近 24 小时失败数"
				cta={<a href="/jobs">查看任务</a>}
				accent="error"
			/>,
		);

		const card = screen.getByText("失败任务").closest('[data-slot="card"]');
		expect(card).not.toBeNull();
		expect(card).toHaveAttribute("data-accent", "error");
		expect(within(card as HTMLElement).getByText("7")).toBeInTheDocument();
		expect(
			within(card as HTMLElement).getByText("最近 24 小时失败数"),
		).toBeInTheDocument();
		expect(
			within(card as HTMLElement).getByRole("link", { name: "查看任务" }),
		).toHaveAttribute("href", "/jobs");
	});

	it("renders MetricCard without optional sections", () => {
		render(<MetricCard label="成功任务" value="12" />);
		expect(screen.getByText("成功任务")).toBeInTheDocument();
		expect(screen.getByText("12")).toBeInTheDocument();
		expect(screen.queryByRole("link")).toBeNull();
	});

	it("renders ErrorStateCard digest details with default surface class", () => {
		const onRetry = vi.fn();
		render(
			<ErrorStateCard
				eyebrow="摘要错误"
				title="读取失败"
				description="服务暂时不可用"
				digest="trace-123"
				titleAs="h1"
				onRetry={onRetry}
			/>,
		);

		const heading = screen.getByRole("heading", { level: 1, name: "读取失败" });
		expect(heading).toBeInTheDocument();
		expect(screen.getByText("trace-123")).toBeInTheDocument();
		expect(heading.closest('[data-slot="card"]')).toHaveClass("folo-surface");
		fireEvent.click(screen.getByRole("button", { name: "Retry page" }));
		expect(onRetry).toHaveBeenCalledTimes(1);
	});

	it("passes expected props through ThemeProvider", () => {
		render(
			<ThemeProvider>
				<div>content</div>
			</ThemeProvider>,
		);

		const provider = screen.getByTestId("next-themes-provider");
		expect(provider).toHaveTextContent("content");
		expect(provider.getAttribute("data-props")).toContain(
			'"attribute":"class"',
		);
		expect(provider.getAttribute("data-props")).toContain(
			'"defaultTheme":"system"',
		);
	});

	it("loads subscriptions in SidebarWrapper and falls back to empty on failure", async () => {
		mockListSubscriptions
			.mockResolvedValueOnce([{ id: "sub-1" }, { id: "sub-2" }])
			.mockRejectedValueOnce(new Error("offline"));

		const successTree = await SidebarWrapper({
			apiHealthState: "healthy",
			apiHealthUrl: "/healthz",
			apiHealthLabel: "正常",
		});
		const failureTree = await SidebarWrapper({
			apiHealthState: "timeout_or_unknown",
			apiHealthUrl: "/healthz",
			apiHealthLabel: "超时",
		});

		const { unmount } = render(successTree);
		expect(screen.getByTestId("sidebar-proxy")).toHaveTextContent(
			"2load-okhealthy/healthz正常",
		);
		unmount();

		render(failureTree);
		expect(screen.getByTestId("sidebar-proxy")).toHaveTextContent(
			"0load-errortimeout_or_unknown/healthz超时",
		);
	});

	it("opens ThemeToggle menu and dispatches theme changes", async () => {
		const user = userEvent.setup();
		render(<ThemeToggle />);

		await user.click(screen.getByRole("button", { name: "Switch theme" }));
		await user.click(screen.getByRole("menuitem", { name: "Light" }));
		await user.click(screen.getByRole("button", { name: "Switch theme" }));
		await user.click(screen.getByRole("menuitem", { name: "Dark" }));
		await user.click(screen.getByRole("button", { name: "Switch theme" }));
		await user.click(screen.getByRole("menuitem", { name: "System" }));

		expect(mockSetTheme).toHaveBeenNthCalledWith(1, "light");
		expect(mockSetTheme).toHaveBeenNthCalledWith(2, "dark");
		expect(mockSetTheme).toHaveBeenNthCalledWith(3, "system");
	}, 15_000);

	it("renders ThemeToggle loading fallback during server render", () => {
		const html = renderToStaticMarkup(<ThemeToggle />);

		expect(html).toContain("Theme menu loading");
		expect(html).not.toContain('aria-label="Theme menu loading"');
		expect(html).not.toContain("Switch theme");
	});

	it("covers dropdown-menu wrappers including portal/shortcut/sub items", () => {
		const onCheckbox = vi.fn();
		const onRadio = vi.fn();

		render(
			<DropdownMenu open>
				<DropdownMenuTrigger>打开菜单</DropdownMenuTrigger>
				<DropdownMenuContent forceMount data-testid="dropdown-content">
					<DropdownMenuGroup>
						<DropdownMenuLabel inset>视图</DropdownMenuLabel>
						<DropdownMenuItem data-testid="dropdown-item-default">
							默认项
						</DropdownMenuItem>
						<DropdownMenuItem
							variant="destructive"
							inset
							data-testid="dropdown-item-danger"
						>
							删除
							<DropdownMenuShortcut>⌘D</DropdownMenuShortcut>
						</DropdownMenuItem>
						<DropdownMenuSeparator />
						<DropdownMenuCheckboxItem checked onCheckedChange={onCheckbox}>
							显示摘要
						</DropdownMenuCheckboxItem>
						<DropdownMenuRadioGroup value="grid" onValueChange={onRadio}>
							<DropdownMenuRadioItem value="grid">网格</DropdownMenuRadioItem>
							<DropdownMenuRadioItem value="list">列表</DropdownMenuRadioItem>
						</DropdownMenuRadioGroup>
					</DropdownMenuGroup>
					<DropdownMenuSub open>
						<DropdownMenuSubTrigger inset>更多</DropdownMenuSubTrigger>
						<DropdownMenuSubContent forceMount>
							<DropdownMenuItem>导出</DropdownMenuItem>
						</DropdownMenuSubContent>
					</DropdownMenuSub>
				</DropdownMenuContent>
				<DropdownMenuPortal>
					<div data-testid="dropdown-portal-marker">portal</div>
				</DropdownMenuPortal>
			</DropdownMenu>,
		);

		expect(screen.getByText("视图")).toHaveAttribute(
			"data-slot",
			"dropdown-menu-label",
		);
		expect(screen.getByTestId("dropdown-item-default")).toHaveAttribute(
			"data-variant",
			"default",
		);
		expect(screen.getByTestId("dropdown-item-danger")).toHaveAttribute(
			"data-variant",
			"destructive",
		);
		expect(screen.getByText("⌘D")).toHaveAttribute(
			"data-slot",
			"dropdown-menu-shortcut",
		);
		fireEvent.click(screen.getByRole("menuitemcheckbox", { name: "显示摘要" }));
		fireEvent.click(screen.getByRole("menuitemradio", { name: "列表" }));
		expect(screen.getByText("导出")).toHaveAttribute(
			"data-slot",
			"dropdown-menu-item",
		);
		expect(screen.getByTestId("dropdown-content")).toHaveAttribute(
			"data-slot",
			"dropdown-menu-content",
		);
		expect(screen.getByTestId("dropdown-portal-marker")).toBeInTheDocument();
		expect(onCheckbox).toHaveBeenCalled();
		expect(onRadio).toHaveBeenCalledWith("list");
	});

	it("covers select wrappers with popper mode", () => {
		render(
			<Select open value="grid" onValueChange={() => {}}>
				<SelectTrigger aria-label="布局切换" size="sm">
					<SelectValue placeholder="选择布局" />
				</SelectTrigger>
				<SelectContent data-testid="select-content-popper">
					<SelectGroup>
						<SelectLabel>视图模式</SelectLabel>
						<SelectItem value="grid">网格</SelectItem>
						<SelectItem value="list">列表</SelectItem>
					</SelectGroup>
					<SelectSeparator />
					<SelectGroup>
						<SelectLabel>密度</SelectLabel>
						<SelectItem value="dense">紧凑</SelectItem>
					</SelectGroup>
				</SelectContent>
			</Select>,
		);

		const popperTrigger = document.querySelector(
			'[data-slot="select-trigger"][aria-label="布局切换"]',
		);
		expect(popperTrigger).not.toBeNull();
		expect(popperTrigger).toHaveAttribute("data-size", "sm");
		const popperContent = screen.getByTestId("select-content-popper");
		expect(within(popperContent).getByText("视图模式")).toHaveAttribute(
			"data-slot",
			"select-label",
		);
		expect(
			within(popperContent).getByRole("option", { name: "网格" }),
		).toHaveAttribute("data-slot", "select-item");
		const selectSeparator = popperContent.querySelector(
			'[data-slot="select-separator"]',
		);
		expect(selectSeparator).not.toBeNull();
		expect(popperContent.className).toContain(
			"data-[side=bottom]:translate-y-1",
		);
	});

	it("covers select wrappers with non-popper mode", () => {
		render(
			<Select open defaultValue="dense">
				<SelectTrigger aria-label="布局切换（默认）">
					<SelectValue placeholder="选择布局" />
				</SelectTrigger>
				<SelectContent
					position="item-aligned"
					data-testid="select-content-aligned"
					className="x-aligned"
				>
					<SelectGroup>
						<SelectLabel>其它布局</SelectLabel>
						<SelectItem value="dense">紧凑</SelectItem>
					</SelectGroup>
				</SelectContent>
			</Select>,
		);

		const alignedTrigger = document.querySelector(
			'[data-slot="select-trigger"][aria-label="布局切换（默认）"]',
		);
		expect(alignedTrigger).not.toBeNull();
		expect(alignedTrigger).toHaveAttribute("data-size", "default");
		const alignedContent = screen.getByTestId("select-content-aligned");
		expect(alignedContent).toHaveClass("x-aligned");
		expect(alignedContent.className).not.toContain(
			"data-[side=bottom]:translate-y-1",
		);
	});

	it("covers ScrollBar horizontal orientation branch", () => {
		const horizontal = ScrollBar({
			orientation: "horizontal",
			className: "x-horizontal",
		} as React.ComponentProps<typeof ScrollBar>);
		expect(horizontal.props.orientation).toBe("horizontal");
		expect(horizontal.props.className).toContain(
			"h-2.5 flex-col border-t border-t-transparent",
		);
		expect(horizontal.props.className).toContain("x-horizontal");
	});

	it("covers Badge variants and asChild rendering", () => {
		render(
			<div>
				<Badge>默认徽标</Badge>
				<Badge variant="ghost">幽灵徽标</Badge>
				<Badge asChild variant="link">
					<a href="/jobs">链接徽标</a>
				</Badge>
			</div>,
		);

		expect(screen.getByText("默认徽标")).toHaveAttribute(
			"data-variant",
			"default",
		);
		expect(screen.getByText("幽灵徽标")).toHaveAttribute(
			"data-variant",
			"ghost",
		);
		expect(screen.getByRole("link", { name: "链接徽标" })).toHaveAttribute(
			"data-variant",
			"link",
		);
	});

	it("covers ErrorStateCard digest and titleAs branches", () => {
		const onRetry = vi.fn();
		const { rerender } = render(
			<ErrorStateCard
				eyebrow="错误"
				title="加载失败"
				description="请稍后重试"
				digest="err-123"
				titleAs="h1"
				onRetry={onRetry}
			/>,
		);

		expect(
			screen.getByRole("heading", { level: 1, name: "加载失败" }),
		).toBeInTheDocument();
		expect(screen.getByText("Error code:")).toBeInTheDocument();
		fireEvent.click(screen.getByRole("button", { name: "Retry page" }));
		expect(onRetry).toHaveBeenCalledTimes(1);

		rerender(
			<ErrorStateCard
				eyebrow="错误"
				title="再次失败"
				description="再试一次"
				onRetry={onRetry}
			/>,
		);
		expect(
			screen.getByRole("heading", { level: 2, name: "再次失败" }),
		).toBeInTheDocument();
		expect(screen.queryByText("Error code:")).toBeNull();
	});

	it("covers ScrollArea root and default vertical scrollbar branches", () => {
		render(
			<ScrollArea className="max-h-24" data-testid="scroll-area-root">
				<div style={{ height: "320px" }}>滚动内容</div>
			</ScrollArea>,
		);

		const root = screen.getByTestId("scroll-area-root");
		expect(root).toHaveAttribute("data-slot", "scroll-area");
		expect(root.className).toContain("relative");
		expect(root.className).toContain("max-h-24");
		expect(
			root.querySelector('[data-slot="scroll-area-viewport"]'),
		).not.toBeNull();

		const vertical = ScrollBar({
			className: "x-vertical",
		} as React.ComponentProps<typeof ScrollBar>);
		expect(vertical.props.orientation).toBe("vertical");
		expect(vertical.props.className).toContain(
			"h-full w-2.5 border-l border-l-transparent",
		);
		expect(vertical.props.className).toContain("x-vertical");
	});
});
