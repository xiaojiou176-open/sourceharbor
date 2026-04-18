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
				className="mx-auto w-full max-w-5xl"
			>
				<h2 id="dashboard-first-route-heading" className="sr-only">
					Choose your first reading route
				</h2>
				<Card className="folo-surface mx-auto w-full border-border/70 bg-gradient-to-br from-background via-background to-rose-50/60">
					<CardHeader className="gap-4">
						<p
							className={`text-xs uppercase tracking-[0.24em] text-muted-foreground ${editorialMono.className}`}
						>
							{copy.kicker}
						</p>
						<h1
							data-route-heading
							tabIndex={-1}
							className={`max-w-4xl text-3xl leading-tight md:text-[2.2rem] ${editorialSerif.className}`}
						>
							{copy.heroTitle}
						</h1>
						<CardDescription className="max-w-3xl text-base leading-7 text-foreground/82">
							Open the reader, scan today&apos;s feed, or follow a few new
							sources. Search and builder tools can wait.
						</CardDescription>
					</CardHeader>
					<CardContent className="space-y-6 pt-0">
						<div className="flex flex-wrap items-center gap-3">
							<Button asChild variant="hero" size="lg">
								<Link href="/reader">{copy.firstHop.evaluatePrimaryCta}</Link>
							</Button>
						</div>
						<p className="text-xs leading-6 text-muted-foreground">
							If you want a softer first step,{" "}
							<Link
								href="/reader/demo"
								className="underline underline-offset-4 hover:text-foreground"
							>
								{copy.firstHop.evaluateSecondaryCta}
							</Link>
							.
						</p>
					</CardContent>
				</Card>
			</section>
		</div>
	);
}
