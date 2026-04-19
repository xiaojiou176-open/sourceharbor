import type { Metadata } from "next";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
} from "@/components/ui/card";
import {
	editorialMono,
	editorialSans,
	editorialSerif,
} from "@/lib/editorial-fonts";
import { getLocaleMessages } from "@/lib/i18n/messages";
import { buildProductMetadata } from "@/lib/seo";

const dashboardCopy = getLocaleMessages().dashboard;

export const metadata: Metadata = buildProductMetadata({
	title: dashboardCopy.metadataTitle,
	description: dashboardCopy.metadataDescription,
	route: "dashboard",
});

export default function DashboardPage() {
	const messages = getLocaleMessages();
	const copy = messages.dashboard;
	return (
		<div
			className={`folo-page-shell folo-unified-shell ${editorialSans.className}`}
		>
			<section
				aria-labelledby="dashboard-first-route-heading"
				className="mx-auto w-full max-w-6xl"
			>
				<h2 id="dashboard-first-route-heading" className="sr-only">
					Choose your first reading route
				</h2>
				<Card className="folo-surface mx-auto w-full border-border/70 bg-gradient-to-br from-background via-background to-rose-50/60">
					<CardHeader className="gap-3 px-5 pb-3 sm:gap-4 sm:px-6">
						<p
							className={`text-xs uppercase tracking-[0.24em] text-muted-foreground ${editorialMono.className}`}
						>
							{copy.kicker}
						</p>
						<h1
							data-route-heading
							tabIndex={-1}
							className={`max-w-3xl text-[1.95rem] leading-[1.08] tracking-[-0.03em] sm:text-3xl md:text-[2.2rem] ${editorialSerif.className}`}
						>
							{copy.heroTitle}
						</h1>
						<CardDescription className="max-w-2xl text-sm leading-6 text-foreground/82 sm:text-base sm:leading-7">
							{copy.heroSubtitle}
						</CardDescription>
					</CardHeader>
					<CardContent className="space-y-4 px-5 pt-0 sm:space-y-5 sm:px-6">
						<div className="flex flex-wrap items-center gap-2.5 sm:gap-3">
							<Button asChild variant="hero" size="lg">
								<Link href="/reader">{copy.firstHop.evaluatePrimaryCta}</Link>
							</Button>
						</div>
						<div className="flex flex-wrap items-center gap-2">
							<Button asChild variant="outline" size="sm">
								<Link href="/feed">{copy.firstHop.operateSecondaryCta}</Link>
							</Button>
							<Button asChild variant="outline" size="sm">
								<Link href="/search">{copy.frontDoors.searchCta}</Link>
							</Button>
							<Button asChild variant="outline" size="sm">
								<Link href="/ask">{copy.frontDoors.askCta}</Link>
							</Button>
						</div>
						<p className="text-xs leading-5 text-muted-foreground">
							If you want a softer first step,{" "}
							<span className="rounded-full border border-border/70 bg-background/80 px-2.5 py-1">
								<Link
									href="/reader/demo"
									className="underline underline-offset-4 hover:text-foreground"
								>
									{copy.firstHop.evaluateSecondaryCta}
								</Link>
							</span>
							.
						</p>
						<section
							aria-labelledby="dashboard-why-now-heading"
							className="grid gap-3 pt-1 sm:grid-cols-3"
						>
							<h2 id="dashboard-why-now-heading" className="sr-only">
								{copy.sectionHeadings.whyNow}
							</h2>
							{[
								{
									title: copy.whyNow.sharedTruthTitle,
									description: copy.whyNow.sharedTruthDescription,
								},
								{
									title: copy.whyNow.proofFirstTitle,
									description: copy.whyNow.proofFirstDescription,
								},
								{
									title: copy.whyNow.returnLoopTitle,
									description: copy.whyNow.returnLoopDescription,
								},
							].map((item) => (
								<div
									key={item.title}
									className="rounded-2xl border border-border/70 bg-background/80 px-4 py-4"
								>
									<p
										className={`text-[11px] uppercase tracking-[0.22em] text-muted-foreground ${editorialMono.className}`}
									>
										{copy.kicker}
									</p>
									<h3
										className={`mt-2 text-lg leading-tight text-foreground ${editorialSerif.className}`}
									>
										{item.title}
									</h3>
									<p className="mt-2 text-sm leading-6 text-foreground/78">
										{item.description}
									</p>
								</div>
							))}
						</section>
					</CardContent>
				</Card>
			</section>
		</div>
	);
}
