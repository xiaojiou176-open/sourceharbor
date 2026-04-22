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
								<>
									<div className="pointer-events-none fixed left-2.5 top-2.5 z-40 md:hidden">
										<div
											aria-hidden="true"
											className="size-9 rounded-full border border-border/45 bg-background/72 backdrop-blur-sm"
										/>
									</div>
									<aside
										aria-hidden="true"
										className="hidden w-[72px] shrink-0 border-r border-border/40 bg-background md:flex"
									/>
								</>
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
							className="flex min-w-0 flex-1 flex-col overflow-auto pl-14 pt-14 md:pl-0 md:pt-0"
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
