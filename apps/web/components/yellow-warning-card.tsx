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
			<CardHeader className="space-y-3 pb-3">
				<div className="flex flex-wrap items-center gap-2">
					<Badge className="border-amber-400/80 bg-amber-100 text-amber-950 hover:bg-amber-100">
						Published with gap
					</Badge>
				</div>
				<h2
					className={`flex items-center gap-2 text-base font-semibold ${editorialSerif.className}`}
				>
					<AlertTriangle className="h-4 w-4 shrink-0" />
					Yellow warning
				</h2>
				<p className="max-w-4xl text-sm leading-6 text-amber-950/80 dark:text-amber-100/80">
					The story is readable, but the proof packet is not fully sealed. Keep
					this note nearby; open the details only if you need the specific
					reasons.
				</p>
			</CardHeader>
			<CardContent className="pt-0">
				<details className="rounded-2xl border border-amber-300/80 bg-white/60 p-4 text-sm dark:border-amber-800/80 dark:bg-amber-950/20">
					<summary className="cursor-pointer list-none font-medium text-amber-950 dark:text-amber-100">
						Read the caution notes
					</summary>
					<div className="mt-3 grid gap-4 lg:grid-cols-[0.78fr_1.22fr]">
						<div>
							<p
								className={`text-[11px] uppercase tracking-[0.22em] text-amber-900/70 dark:text-amber-100/70 ${editorialMono.className}`}
							>
								How to read safely
							</p>
							<ol className="mt-2 space-y-2 leading-6">
								<li>1. Read the body first.</li>
								<li>2. Open source notes before reusing a claim.</li>
								<li>3. Check repair and coverage last.</li>
							</ol>
						</div>
						<div className="border-t border-amber-300/80 pt-4 dark:border-amber-800/80 lg:border-l lg:border-t-0 lg:pl-4 lg:pt-0">
							<p
								className={`text-[11px] uppercase tracking-[0.22em] text-amber-900/70 dark:text-amber-100/70 ${editorialMono.className}`}
							>
								Why this note exists
							</p>
							<ul className="mt-2 list-disc space-y-2 pl-5 leading-6">
								{reasons.map((reason) => (
									<li key={reason}>{reason}</li>
								))}
							</ul>
						</div>
					</div>
				</details>
			</CardContent>
		</Card>
	);
}
