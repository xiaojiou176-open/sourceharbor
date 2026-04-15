import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import type { Metadata } from "next";
import { Suspense } from "react";

import { FormValidationController } from "@/components/form-validation-controller";
import { RouteTransition } from "@/components/route-transition";
import { SidebarWrapper } from "@/components/sidebar-wrapper";
import { ThemeProvider } from "@/components/theme-provider";
import { fetchApiHealthState } from "@/lib/api/health";
import { buildApiUrl } from "@/lib/api/url";
import { buildAppShellMetadata } from "@/lib/seo";

import "./globals.css";

export const metadata: Metadata = buildAppShellMetadata();

const HEALTH_TIMEOUT_MS = 2000;

export default async function RootLayout({
	children,
}: Readonly<{ children: React.ReactNode }>) {
	const healthUrl = buildApiUrl("/healthz");
	const healthState = await fetchApiHealthState({
		timeoutMs: HEALTH_TIMEOUT_MS,
	});
	const healthLabel =
		healthState === "healthy"
			? "Healthy"
			: healthState === "unhealthy"
				? "Unhealthy"
				: "Timeout / Unknown";

	return (
		<html
			lang="en"
			suppressHydrationWarning
			className={`${GeistSans.variable} ${GeistMono.variable}`}
		>
			<body className="font-sans antialiased">
				<a className="skip-link" href="#main-content">
					Skip to main content
				</a>
				<ThemeProvider>
					<div className="flex h-screen overflow-hidden bg-background">
						<Suspense
							fallback={
								<aside className="w-[240px] shrink-0 border-r border-border bg-sidebar" />
							}
						>
							<SidebarWrapper
								apiHealthState={healthState}
								apiHealthUrl={healthUrl}
								apiHealthLabel={healthLabel}
							/>
						</Suspense>
						<main
							id="main-content"
							className="flex min-w-0 flex-1 flex-col overflow-auto pt-14 md:pt-0"
							tabIndex={-1}
						>
							<div className="folo-main-stage">
								<RouteTransition>{children}</RouteTransition>
							</div>
						</main>
					</div>
				</ThemeProvider>
				<FormValidationController />
			</body>
		</html>
	);
}
