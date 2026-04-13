import { AlertTriangle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import {
	editorialMono,
	editorialSans,
	editorialSerif,
} from "@/lib/editorial-fonts";

type YellowWarningCardProps = {
	reasons: string[];
};

export function YellowWarningCard({ reasons }: YellowWarningCardProps) {
	return (
		<Card
			className={`border-amber-300 bg-amber-50/92 text-amber-950 shadow-sm dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-100 ${editorialSans.className}`}
		>
			<CardHeader className="space-y-4 pb-3">
				<div className="flex flex-wrap items-center gap-2">
					<Badge className="border-amber-400/80 bg-amber-100 text-amber-950 hover:bg-amber-100">
						Published with gap
					</Badge>
					<Badge
						variant="outline"
						className="border-amber-400/80 text-amber-900 dark:border-amber-700 dark:text-amber-100"
					>
						Reading contract
					</Badge>
				</div>
				<p
					className={`text-[11px] uppercase tracking-[0.22em] text-amber-900/70 dark:text-amber-100/70 ${editorialMono.className}`}
				>
					Keep this in the margin
				</p>
				<h2
					className={`flex items-center gap-2 text-lg font-semibold ${editorialSerif.className}`}
				>
					<AlertTriangle className="h-4 w-4 shrink-0" />
					Yellow warning
				</h2>
				<p className="max-w-4xl text-sm leading-6 text-amber-950/80 dark:text-amber-100/80">
					The story is readable, but the proof packet is not fully sealed. Treat
					this panel like the contract taped beside an article: it tells you
					what the warning means, how to read safely, and why the caution exists
					without pulling you away from the body.
				</p>
			</CardHeader>
			<CardContent className="grid gap-4 text-sm md:grid-cols-[0.9fr_1.1fr]">
				<section className="rounded-2xl border border-amber-300/80 bg-white/60 p-4 dark:border-amber-800/80 dark:bg-amber-950/20">
					<h3 className="font-medium">What this means</h3>
					<p className="mt-2 leading-6">
						One or more evidence lanes are missing or degraded, so the body is
						informative but not fully sealed for quoting or downstream reuse.
					</p>
				</section>
				<section className="rounded-2xl border border-amber-300/80 bg-white/60 p-4 dark:border-amber-800/80 dark:bg-amber-950/20">
					<div className="grid gap-4 lg:grid-cols-[0.78fr_1.22fr]">
						<div>
							<h3 className="font-medium">How to read safely</h3>
							<ol className="mt-2 space-y-2 leading-6">
								<li>1. Read the body first.</li>
								<li>2. Open the footnote drawer before reusing a claim.</li>
								<li>3. Check coverage last.</li>
							</ol>
						</div>
						<div className="border-t border-amber-300/80 pt-4 dark:border-amber-800/80 lg:border-l lg:border-t-0 lg:pl-4 lg:pt-0">
							<h3 className="font-medium">Why this warning exists</h3>
							<ul className="mt-2 list-disc space-y-2 pl-5 leading-6">
								{reasons.map((reason) => (
									<li key={reason}>{reason}</li>
								))}
							</ul>
						</div>
					</div>
				</section>
			</CardContent>
		</Card>
	);
}
