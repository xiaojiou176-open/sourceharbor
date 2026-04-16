"use client";

import {
	Activity,
	Blocks,
	BookmarkPlus,
	FileText,
	Home,
	Inbox,
	Layers3,
	LineChart,
	List,
	ListTodo,
	type LucideIcon,
	Menu,
	MessageSquare,
	PanelLeftClose,
	Plus,
	Search,
	Settings,
	Sparkles,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
	Sheet,
	SheetContent,
	SheetDescription,
	SheetTitle,
	SheetTrigger,
} from "@/components/ui/sheet";
import type { Subscription, SubscriptionCategory } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const CATEGORY_ORDER: SubscriptionCategory[] = [
	"tech",
	"creator",
	"macro",
	"ops",
	"misc",
];
const CATEGORY_LABELS: Record<SubscriptionCategory, string> = {
	tech: "Tech",
	creator: "Creator",
	macro: "Macro",
	ops: "Operations",
	misc: "Other",
};

function groupByCategory(
	subs: Subscription[],
): Map<SubscriptionCategory, Subscription[]> {
	const map = new Map<SubscriptionCategory, Subscription[]>();
	for (const cat of CATEGORY_ORDER) {
		map.set(cat, []);
	}
	for (const sub of subs) {
		const cat =
			sub.category in CATEGORY_LABELS
				? (sub.category as SubscriptionCategory)
				: "misc";
		const list = map.get(cat) ?? [];
		list.push(sub);
		map.set(cat, list);
	}
	return map;
}

type ApiHealthState = "healthy" | "unhealthy" | "timeout_or_unknown";

type SidebarProps = {
	subscriptions: Subscription[];
	subscriptionsLoadError?: boolean;
	apiHealthState: ApiHealthState;
	apiHealthUrl: string;
	apiHealthLabel: string;
};

type NavContentProps = {
	collapsed: boolean;
	subscriptions: Subscription[];
	subscriptionsLoadError: boolean;
	apiHealthState: ApiHealthState;
	apiHealthUrl: string;
	apiHealthLabel: string;
};

type NavItem = {
	href: string;
	label: string;
	icon: LucideIcon;
	active: boolean;
};

type NavSection = {
	id: string;
	label: string;
	items: NavItem[];
};

function SidebarNavContent({
	collapsed,
	subscriptions,
	subscriptionsLoadError,
	apiHealthState,
	apiHealthUrl,
	apiHealthLabel,
}: NavContentProps) {
	const pathname = usePathname();
	const searchParams = useSearchParams();
	const frontstageFocused =
		pathname === "/" ||
		pathname.startsWith("/reader") ||
		pathname.startsWith("/feed") ||
		pathname.startsWith("/subscriptions");
	const currentCategory = searchParams.get("category") ?? "";
	const currentSub = searchParams.get("sub") ?? "";
	const isFeed = pathname === "/feed" || pathname.startsWith("/feed");
	const utilityOpen =
		pathname.startsWith("/builders") ||
		pathname.startsWith("/mcp") ||
		pathname.startsWith("/ops") ||
		pathname.startsWith("/jobs") ||
		pathname.startsWith("/ingest-runs");
	const followedSourcesOpen = Boolean(
		isFeed ||
			pathname.startsWith("/subscriptions") ||
			currentCategory ||
			currentSub,
	);
	const grouped = groupByCategory(subscriptions);
	const enabledSubs = subscriptions.filter((s) => s.enabled);
	const navSections: NavSection[] = [
		{
			id: "read",
			label: "Read",
			items: frontstageFocused
				? [
						{ href: "/", label: "Home", icon: Home, active: pathname === "/" },
						{
							href: "/reader",
							label: "Reader",
							icon: FileText,
							active: pathname.startsWith("/reader"),
						},
						{
							href: "/feed",
							label: "Reading desk",
							icon: Sparkles,
							active: isFeed && !currentCategory && !currentSub,
						},
						{
							href: "/subscriptions",
							label: "Sources",
							icon: Plus,
							active: pathname.startsWith("/subscriptions"),
						},
					]
				: [
						{ href: "/", label: "Home", icon: Home, active: pathname === "/" },
						{
							href: "/reader",
							label: "Reader",
							icon: FileText,
							active: pathname.startsWith("/reader"),
						},
						{
							href: "/feed",
							label: "Reading desk",
							icon: Sparkles,
							active: isFeed && !currentCategory && !currentSub,
						},
						{
							href: "/subscriptions",
							label: "Sources",
							icon: Plus,
							active: pathname.startsWith("/subscriptions"),
						},
						{
							href: "/search",
							label: "Search",
							icon: Search,
							active: pathname.startsWith("/search"),
						},
						{
							href: "/ask",
							label: "Ask",
							icon: MessageSquare,
							active: pathname.startsWith("/ask"),
						},
					],
		},
		{
			id: "build",
			label: "Developers",
			items: [
				{
					href: "/builders",
					label: "Developer tools",
					icon: Blocks,
					active: pathname.startsWith("/builders"),
				},
				{
					href: "/mcp",
					label: "Assistant tools",
					icon: List,
					active: pathname.startsWith("/mcp"),
				},
			],
		},
		{
			id: "compounder",
			label: "Follow",
			items: [
				{
					href: "/watchlists",
					label: "Saved topics",
					icon: BookmarkPlus,
					active: pathname.startsWith("/watchlists"),
				},
				{
					href: "/trends",
					label: "What changed",
					icon: LineChart,
					active: pathname.startsWith("/trends"),
				},
				{
					href: "/briefings",
					label: "Story briefs",
					icon: FileText,
					active: pathname.startsWith("/briefings"),
				},
				{
					href: "/knowledge",
					label: "Source notes",
					icon: Layers3,
					active: pathname.startsWith("/knowledge"),
				},
			],
		},
		{
			id: "operate",
			label: "System",
			items: [
				{
					href: "/ops",
					label: "System status",
					icon: Activity,
					active: pathname.startsWith("/ops"),
				},
				{
					href: "/jobs",
					label: "Processing history",
					icon: ListTodo,
					active: pathname.startsWith("/jobs"),
				},
				{
					href: "/ingest-runs",
					label: "Import history",
					icon: Inbox,
					active: pathname.startsWith("/ingest-runs"),
				},
			],
		},
	];
	const primarySections = navSections.filter(
		(section) =>
			section.id === "read" ||
			(!frontstageFocused && section.id === "compounder"),
	);
	const utilitySections = navSections.filter(
		(section) =>
			!frontstageFocused &&
			(section.id === "build" || section.id === "operate"),
	);

	return (
		<>
			<nav aria-label="Primary navigation" className="flex flex-col gap-3 p-3">
				{primarySections.map((section, sectionIndex) => (
					<div key={section.id} className="space-y-1.5">
						{!collapsed ? (
							<p
								className={cn(
									"px-3 text-[11px] font-semibold uppercase tracking-[0.22em] text-muted-foreground",
									sectionIndex > 0 ? "pt-2" : "",
								)}
							>
								{section.label}
							</p>
						) : null}
						{section.items.map((item) => {
							const Icon = item.icon;
							return (
								<Link
									key={item.href}
									href={item.href}
									className={cn(
										"flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200 motion-reduce:transition-none",
										item.active
											? "bg-sidebar-accent text-sidebar-accent-foreground"
											: "text-sidebar-foreground/90 hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground",
									)}
									aria-current={item.active ? "page" : undefined}
								>
									<Icon className="size-4 shrink-0 opacity-80" aria-hidden />
									<span className={collapsed ? "sr-only" : undefined}>
										{item.label}
									</span>
								</Link>
							);
						})}
					</div>
				))}

				{utilitySections.length > 0 ? (
					<details
						className="rounded-xl border border-border/60 bg-background/60"
						open={collapsed || utilityOpen}
					>
						<summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-3 py-2 marker:content-none [&::-webkit-details-marker]:hidden">
							<div className="space-y-1">
								<p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
									Tools and status
								</p>
								{!collapsed ? (
									<p className="text-xs text-muted-foreground">
										Open this only when you are setting up or checking the
										system.
									</p>
								) : null}
							</div>
							{!collapsed ? (
								<span className="rounded-full border border-border/60 bg-background/80 px-2 py-0.5 text-[11px] text-muted-foreground">
									{utilityOpen ? "Open" : "Later"}
								</span>
							) : null}
						</summary>
						<div className="border-t border-border/50 px-2 pb-2 pt-2">
							{utilitySections.map((section) => (
								<div key={section.id} className="space-y-1.5">
									{!collapsed ? (
										<p className="px-2 text-[11px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
											{section.label}
										</p>
									) : null}
									{section.items.map((item) => {
										const Icon = item.icon;
										return (
											<Link
												key={item.href}
												href={item.href}
												className={cn(
													"flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200 motion-reduce:transition-none",
													item.active
														? "bg-sidebar-accent text-sidebar-accent-foreground"
														: "text-sidebar-foreground/90 hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground",
												)}
												aria-current={item.active ? "page" : undefined}
											>
												<Icon
													className="size-4 shrink-0 opacity-80"
													aria-hidden
												/>
												<span className={collapsed ? "sr-only" : undefined}>
													{item.label}
												</span>
											</Link>
										);
									})}
								</div>
							))}
						</div>
					</details>
				) : null}

				{subscriptionsLoadError && !collapsed && !frontstageFocused ? (
					<div
						className="mx-1 mt-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2"
						aria-live="polite"
						aria-atomic="true"
					>
						<p className="text-xs text-destructive">
							Could not load your followed sources. Retry from Following.
						</p>
						<Link
							href="/subscriptions"
							className="mt-1 inline-flex text-xs font-medium text-destructive underline underline-offset-2"
						>
							Open Following
						</Link>
					</div>
				) : null}

				{enabledSubs.length > 0 && !collapsed && !frontstageFocused ? (
					<details
						className="rounded-xl border border-border/60 bg-background/60"
						open={followedSourcesOpen}
					>
						<summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-3 py-2 marker:content-none [&::-webkit-details-marker]:hidden">
							<div className="space-y-1">
								<p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
									Your followed sources
								</p>
								<p className="text-xs leading-5 text-muted-foreground">
									Open this only when you already know the source you want.
								</p>
							</div>
							<span className="rounded-full border border-border/60 bg-background/80 px-2 py-0.5 text-[11px] text-muted-foreground">
								{followedSourcesOpen ? "Open" : "Later"}
							</span>
						</summary>
						<div className="border-t border-border/50 px-2 pb-2 pt-2">
							{CATEGORY_ORDER.map((cat) => {
								const list = grouped.get(cat)?.filter((s) => s.enabled) ?? [];
								if (list.length === 0) return null;
								return (
									<div key={cat} className="space-y-0.5">
										<Link
											href={`/feed?category=${cat}`}
											className={cn(
												"flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-semibold uppercase tracking-wider transition-all duration-200 motion-reduce:transition-none",
												currentCategory === cat
													? "bg-sidebar-accent text-sidebar-accent-foreground"
													: "text-muted-foreground hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground",
											)}
											aria-current={
												currentCategory === cat ? "page" : undefined
											}
										>
											<List
												className="size-3 shrink-0 opacity-70"
												aria-hidden
											/>
											{CATEGORY_LABELS[cat]}
										</Link>
										<ul className="ml-4 space-y-0.5 border-l border-border/40 pl-2">
											{list.map((sub) => (
												<li key={sub.id}>
													<Link
														href={`/feed?sub=${encodeURIComponent(sub.id)}`}
														className={cn(
															"block truncate rounded px-2 py-1 text-sm",
															currentSub === sub.id
																? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
																: "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
														)}
														title={sub.source_name}
														aria-current={
															currentSub === sub.id ? "page" : undefined
														}
													>
														{sub.source_name || sub.source_value || "Untitled"}
													</Link>
												</li>
											))}
										</ul>
									</div>
								);
							})}
						</div>
					</details>
				) : null}
			</nav>

			<div className="border-t border-border/40 p-3">
				<div className="flex flex-col gap-0.5">
					{!frontstageFocused ? (
						<>
							<Link
								href="/settings"
								className={cn(
									"flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200 motion-reduce:transition-none",
									pathname.startsWith("/settings")
										? "bg-sidebar-accent text-sidebar-accent-foreground"
										: "text-sidebar-foreground/90 hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground",
								)}
								aria-current={
									pathname.startsWith("/settings") ? "page" : undefined
								}
							>
								<Settings className="size-4 shrink-0 opacity-80" aria-hidden />
								<span className={collapsed ? "sr-only" : undefined}>
									Settings
								</span>
							</Link>
							<Separator className="my-2" />
						</>
					) : null}
					<div
						className={cn(
							"flex items-center px-2 py-1",
							collapsed ? "justify-center" : "justify-between",
						)}
					>
						{!collapsed ? (
							<span className="text-xs text-muted-foreground">Theme</span>
						) : null}
						<ThemeToggle />
					</div>
					{!collapsed && !frontstageFocused ? (
						<a
							href={apiHealthUrl}
							target="_blank"
							rel="noreferrer"
							className="api-health-chip api-health-chip-sidebar mt-1 flex items-center gap-2 rounded-lg px-2 py-1.5 text-xs"
							aria-live="polite"
						>
							<span
								className={`api-health-dot api-health-dot-${apiHealthState}`}
								aria-hidden
							/>
							<span className="text-muted-foreground">
								API health: {apiHealthLabel}
							</span>
						</a>
					) : null}
				</div>
			</div>
		</>
	);
}

export function Sidebar({
	subscriptions,
	subscriptionsLoadError = false,
	apiHealthState,
	apiHealthUrl,
	apiHealthLabel,
}: SidebarProps) {
	const pathname = usePathname();
	const [collapsed, setCollapsed] = useState(false);
	const [isMobile, setIsMobile] = useState(false);
	const frontstageFocused =
		pathname === "/" ||
		pathname.startsWith("/reader") ||
		pathname.startsWith("/feed") ||
		pathname.startsWith("/subscriptions");

	useEffect(() => {
		if (
			typeof window === "undefined" ||
			typeof window.matchMedia !== "function"
		) {
			return;
		}
		const mediaQuery = window.matchMedia("(max-width: 768px)");
		const syncCollapsed = () => {
			const mobile = mediaQuery.matches;
			setIsMobile(mobile);
			setCollapsed(mobile || frontstageFocused);
		};
		syncCollapsed();
		mediaQuery.addEventListener("change", syncCollapsed);
		return () => {
			mediaQuery.removeEventListener("change", syncCollapsed);
		};
	}, [frontstageFocused]);

	if (isMobile) {
		return (
			<div className="pointer-events-none fixed left-3 top-3 z-40 md:hidden">
				<Sheet>
					<SheetTrigger asChild>
						<Button
							variant="outline"
							size="icon"
							aria-label="Open navigation panel"
							className="pointer-events-auto rounded-full border-border/70 bg-background/95 shadow-sm backdrop-blur"
						>
							<Menu className="size-4" />
						</Button>
					</SheetTrigger>
					<SheetContent side="left" className="w-[280px] p-0">
						<SheetTitle className="sr-only">Mobile navigation</SheetTitle>
						<SheetDescription className="sr-only">
							Open page navigation, subscription groups, and global status
							shortcuts on mobile.
						</SheetDescription>
						<aside
							aria-label="Sidebar navigation"
							className="flex h-full flex-col bg-background"
						>
							<ScrollArea className="flex-1">
								<SidebarNavContent
									collapsed={false}
									subscriptions={subscriptions}
									subscriptionsLoadError={subscriptionsLoadError}
									apiHealthState={apiHealthState}
									apiHealthUrl={apiHealthUrl}
									apiHealthLabel={apiHealthLabel}
								/>
							</ScrollArea>
						</aside>
					</SheetContent>
				</Sheet>
			</div>
		);
	}

	return (
		<aside
			className={cn(
				"flex shrink-0 flex-col border-r border-border/40 bg-background transition-[width] duration-200 motion-reduce:transition-none",
				collapsed ? "w-[72px]" : "w-[216px]",
			)}
			aria-label="Sidebar navigation"
		>
			<div className="flex items-center justify-between border-b border-border/40 px-3 py-3">
				{collapsed ? (
					<Sheet>
						<SheetTrigger asChild>
							<Button
								variant="ghost"
								size="icon"
								aria-label="Open navigation panel"
							>
								<Menu className="size-4" />
							</Button>
						</SheetTrigger>
						<SheetContent side="left" className="w-[280px] p-0">
							<SheetTitle className="sr-only">Collapsed navigation</SheetTitle>
							<SheetDescription className="sr-only">
								Open page navigation, subscription groups, and global status
								shortcuts while the desktop rail is collapsed.
							</SheetDescription>
							<aside
								aria-label="Sidebar navigation"
								className="flex h-full flex-col bg-background"
							>
								<ScrollArea className="flex-1">
									<SidebarNavContent
										collapsed={false}
										subscriptions={subscriptions}
										subscriptionsLoadError={subscriptionsLoadError}
										apiHealthState={apiHealthState}
										apiHealthUrl={apiHealthUrl}
										apiHealthLabel={apiHealthLabel}
									/>
								</ScrollArea>
							</aside>
						</SheetContent>
					</Sheet>
				) : (
					<div className="min-w-0">
						<p className="text-sm font-semibold tracking-tight text-foreground">
							SourceHarbor
						</p>
						<p className="text-xs text-muted-foreground">Read first</p>
					</div>
				)}
				<Button
					type="button"
					variant="ghost"
					size="icon"
					aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
					onClick={() => setCollapsed((value) => !value)}
				>
					<PanelLeftClose
						className={cn(
							"size-4 transition-transform motion-reduce:transition-none",
							collapsed && "rotate-180",
						)}
					/>
				</Button>
			</div>
			<ScrollArea className="flex-1">
				<SidebarNavContent
					collapsed={collapsed}
					subscriptions={subscriptions}
					subscriptionsLoadError={subscriptionsLoadError}
					apiHealthState={apiHealthState}
					apiHealthUrl={apiHealthUrl}
					apiHealthLabel={apiHealthLabel}
				/>
			</ScrollArea>
		</aside>
	);
}
