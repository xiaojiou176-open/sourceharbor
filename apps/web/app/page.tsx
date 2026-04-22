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
					<CardContent className="px-5 pt-0 sm:px-6">
						<div className="grid gap-6 md:grid-cols-[minmax(0,1.05fr)_minmax(280px,0.95fr)]">
							<div className="space-y-4 sm:space-y-5">
								<div className="flex flex-wrap items-center gap-2.5 sm:gap-3">
									<Button asChild variant="hero" size="lg">
										<Link href="/reader">
											{copy.firstHop.evaluatePrimaryCta}
										</Link>
									</Button>
								</div>
								<p className="text-xs leading-5 text-muted-foreground">
									Need a softer sample?{" "}
									<Link
										href="/reader/demo"
										className="underline underline-offset-4 hover:text-foreground"
									>
										{copy.firstHop.evaluateSecondaryCta}
									</Link>
									. Need the reading desk instead?{" "}
									<Link
										href="/feed"
										className="underline underline-offset-4 hover:text-foreground"
									>
										{copy.firstHop.operateSecondaryCta}
									</Link>
									.
								</p>
								<section
									aria-labelledby="dashboard-why-now-heading"
									className="pt-1"
								>
									<h2 id="dashboard-why-now-heading" className="sr-only">
										{copy.sectionHeadings.whyNow}
									</h2>
									<p className="rounded-2xl border border-border/70 bg-background/78 px-4 py-3 text-sm leading-6 text-foreground/74">
										{copy.whyNowCompact}
									</p>
								</section>
							</div>
							<div className="space-y-3 rounded-[1.5rem] border border-border/70 bg-background/85 p-4">
								<p
									className={`text-[11px] uppercase tracking-[0.22em] text-muted-foreground ${editorialMono.className}`}
								>
									Reading specimen
								</p>
								<div className="rounded-[1.35rem] border border-border/60 bg-background/92 px-4 py-4 shadow-[0_18px_42px_-34px_rgba(15,23,42,0.2)]">
									<p
										className={`text-[10px] uppercase tracking-[0.22em] text-muted-foreground ${editorialMono.className}`}
									>
										Finished reader
									</p>
									<h2
										className={`mt-3 text-[1.45rem] leading-[1.05] tracking-[-0.028em] text-foreground ${editorialSerif.className}`}
									>
										Bilibili history milestone:
										<br />
										the earliest surviving AV2.
									</h2>
									<p className="mt-3 text-sm leading-6 text-foreground/78">
										One note worth continuing, a short excerpt worth trusting,
										and proof that stays nearby instead of taking over the page.
									</p>
									<div className="mt-3 rounded-2xl border border-border/55 bg-background/80 px-3 py-3">
										<p
											className={`text-[10px] uppercase tracking-[0.2em] text-muted-foreground ${editorialMono.className}`}
										>
											Why it matters
										</p>
										<p className="mt-2 text-[13px] leading-6 text-foreground/72">
											Decide whether this belongs in the reading loop before
											filters, settings, or builder rails ask for your
											attention.
										</p>
									</div>
									<div className="mt-4 flex flex-wrap gap-2">
										{[
											"Finished reader",
											"Readable title",
											"Proof one click away",
										].map((item) => (
											<span
												key={item}
												className="rounded-full border border-border/65 bg-background/80 px-3 py-1 text-[11px] text-foreground/72"
											>
												{item}
											</span>
										))}
									</div>
									<p className="mt-4 text-sm leading-6 text-foreground/72">
										If the sample earns a second read, open the timeline,
										search, or source desk on purpose instead of starting there.
									</p>
								</div>
							</div>
						</div>
					</CardContent>
				</Card>
			</section>
		</div>
	);
}
