import { AlertTriangle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

type YellowWarningCardProps = {
	reasons: string[];
};

export function YellowWarningCard({ reasons }: YellowWarningCardProps) {
	return (
		<Card className="border-amber-300 bg-amber-50/90 text-amber-950 shadow-sm dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-100">
			<CardHeader className="space-y-4 pb-3">
				<div className="flex flex-wrap items-center gap-2">
					<Badge className="border-amber-400/80 bg-amber-100 text-amber-950 hover:bg-amber-100">
						Published with gap
					</Badge>
					<Badge
						variant="outline"
						className="border-amber-400/80 text-amber-900 dark:border-amber-700 dark:text-amber-100"
					>
						Readable, not fully sealed
					</Badge>
				</div>
				<h2 className="flex items-center gap-2 text-lg font-semibold">
					<AlertTriangle className="h-4 w-4 shrink-0" />
					Yellow warning
				</h2>
				<p className="max-w-4xl text-sm leading-6 text-amber-950/80 dark:text-amber-100/80">
					The story is readable, but the proof packet is not fully sealed. Keep
					reading, then check the evidence drawer before you quote or reuse a
					claim.
				</p>
				<div className="flex flex-wrap gap-2 text-xs font-medium">
					<Badge
						variant="outline"
						className="border-amber-400/80 text-amber-950 dark:border-amber-700 dark:text-amber-100"
					>
						Read the body
					</Badge>
					<Badge
						variant="outline"
						className="border-amber-400/80 text-amber-950 dark:border-amber-700 dark:text-amber-100"
					>
						Keep the warning in mind
					</Badge>
					<Badge
						variant="outline"
						className="border-amber-400/80 text-amber-950 dark:border-amber-700 dark:text-amber-100"
					>
						Open evidence only when needed
					</Badge>
				</div>
			</CardHeader>
			<CardContent className="space-y-4 text-sm">
				<div className="rounded-2xl border border-amber-300/80 bg-white/60 p-4 dark:border-amber-800/80 dark:bg-amber-950/20">
					<p className="font-medium">What this means</p>
					<p className="mt-2 leading-6">
						One or more evidence lanes are missing or degraded, so the body is
						informative but not fully sealed.
					</p>
				</div>
				<details className="rounded-2xl border border-amber-300/80 bg-white/60 p-4 dark:border-amber-800/80 dark:bg-amber-950/20">
					<summary className="m-[-0.5rem] cursor-pointer list-none rounded-xl p-2 transition-colors hover:bg-amber-100/70 dark:hover:bg-amber-900/20">
						<span className="font-medium">Open full warning context</span>
					</summary>
					<div className="mt-4 grid gap-5 md:grid-cols-2">
						<div className="space-y-1">
							<p className="font-medium">Safe reading checklist</p>
							<ul className="list-disc space-y-1 pl-5">
								<li>Read the body first.</li>
								<li>
									Open the source contribution drawer before reusing a claim.
								</li>
								<li>Check coverage last.</li>
							</ul>
						</div>
						<div className="space-y-1">
							<p className="font-medium">Why this warning exists</p>
							<ul className="list-disc space-y-1 pl-5">
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
