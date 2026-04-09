"use client";

import { usePathname } from "next/navigation";
import { type ReactNode, useEffect, useMemo, useRef } from "react";
import { getLocaleMessages } from "@/lib/i18n/messages";

type RouteTransitionProps = {
	children: ReactNode;
};

const routeTransitionCopy = getLocaleMessages().routeTransition;
const ROUTE_NAME_MAP: Array<{
	href: string;
	label: (typeof routeTransitionCopy.labels)[keyof typeof routeTransitionCopy.labels];
}> = [
	{ href: "/", label: routeTransitionCopy.labels.home },
	{ href: "/subscriptions", label: routeTransitionCopy.labels.subscriptions },
	{ href: "/search", label: routeTransitionCopy.labels.search },
	{ href: "/ask", label: routeTransitionCopy.labels.ask },
	{ href: "/mcp", label: routeTransitionCopy.labels.mcp },
	{ href: "/ops", label: routeTransitionCopy.labels.ops },
	{ href: "/reader", label: routeTransitionCopy.labels.reader },
	{ href: "/watchlists", label: routeTransitionCopy.labels.watchlists },
	{ href: "/trends", label: routeTransitionCopy.labels.trends },
	{ href: "/briefings", label: routeTransitionCopy.labels.briefings },
	{ href: "/playground", label: routeTransitionCopy.labels.playground },
	{ href: "/proof", label: routeTransitionCopy.labels.proof },
	{ href: "/knowledge", label: routeTransitionCopy.labels.knowledge },
	{ href: "/jobs", label: routeTransitionCopy.labels.jobs },
	{ href: "/ingest-runs", label: routeTransitionCopy.labels.ingestRuns },
	{ href: "/feed", label: routeTransitionCopy.labels.feed },
	{ href: "/settings", label: routeTransitionCopy.labels.settings },
	{ href: "/use-cases", label: routeTransitionCopy.labels.useCases },
];

function getRouteLabel(pathname: string | null): string {
	const normalizedPath = pathname ?? "/";
	for (const route of ROUTE_NAME_MAP) {
		if (
			route.href === "/"
				? normalizedPath === "/"
				: normalizedPath === route.href ||
					normalizedPath.startsWith(`${route.href}/`)
		) {
			return route.label;
		}
	}
	return routeTransitionCopy.labels.page;
}

export function RouteTransition({ children }: RouteTransitionProps) {
	const pathname = usePathname();
	const transitionRef = useRef<HTMLDivElement>(null);
	const routeLabel = useMemo(() => getRouteLabel(pathname), [pathname]);
	const lastFocusedHeadingRef = useRef<HTMLElement | null>(null);

	useEffect(() => {
		const transitionElement = transitionRef.current;
		if (!transitionElement) {
			return;
		}
		const currentPathname = pathname ?? "/";
		if (transitionElement.getAttribute("data-route") !== currentPathname) {
			return;
		}

		const focusMainHeading = () => {
			let targetHeading: HTMLElement | null = null;
			const selectors = ["[data-route-heading]", "h1", "h2"];
			for (const selector of selectors) {
				targetHeading = transitionElement.querySelector<HTMLElement>(selector);
				if (targetHeading) {
					break;
				}
			}
			if (!targetHeading) {
				return;
			}

			const prev = lastFocusedHeadingRef.current;
			if (prev && prev !== targetHeading) {
				prev.removeAttribute("tabindex");
			}

			if (!targetHeading.hasAttribute("tabindex")) {
				targetHeading.setAttribute("tabindex", "-1");
			}
			lastFocusedHeadingRef.current = targetHeading;
			targetHeading.focus({ preventScroll: true });
		};

		const frameId = window.requestAnimationFrame(focusMainHeading);
		return () => {
			window.cancelAnimationFrame(frameId);
			const prev = lastFocusedHeadingRef.current;
			if (prev) {
				prev.removeAttribute("tabindex");
				lastFocusedHeadingRef.current = null;
			}
		};
	}, [pathname]);

	return (
		<div
			ref={transitionRef}
			key={pathname}
			className="route-transition route-transition-enter folo-route-layer"
			data-route={pathname}
		>
			<div aria-hidden="true" className="route-progress-indicator">
				<div aria-hidden="true" className="route-progress-bar" />
			</div>
			<output className="sr-only" aria-live="polite" aria-atomic="true">
				{routeTransitionCopy.announcementPrefix} {routeLabel}
			</output>
			{children}
		</div>
	);
}
