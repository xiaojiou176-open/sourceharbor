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
			</CardHeader>
			<CardContent className="space-y-5 text-sm">
				<div className="grid gap-3 md:grid-cols-3">
					<div className="rounded-2xl border border-amber-300/80 bg-white/60 p-4 dark:border-amber-800/80 dark:bg-amber-950/20">
						<p className="font-medium">What this means</p>
						<p className="mt-2 leading-6">
							One or more evidence lanes are missing or degraded, so the body is
							informative but not fully sealed.
						</p>
					</div>
					<div className="rounded-2xl border border-amber-300/80 bg-white/60 p-4 dark:border-amber-800/80 dark:bg-amber-950/20">
						<p className="font-medium">How to read safely</p>
						<p className="mt-2 leading-6">
							Use the body for orientation first, then open provenance before
							you export a claim into another workflow.
						</p>
					</div>
					<div className="rounded-2xl border border-amber-300/80 bg-white/60 p-4 dark:border-amber-800/80 dark:bg-amber-950/20">
						<p className="font-medium">What not to assume</p>
						<p className="mt-2 leading-6">
							Do not treat a yellow-warning document as the final proof packet
							just because the narrative already reads well.
						</p>
					</div>
				</div>
				<div className="space-y-1">
					<p className="font-medium">Safe reading checklist</p>
					<ul className="list-disc space-y-1 pl-5">
						<li>Read the body first.</li>
						<li>Open the source contribution drawer before reusing a claim.</li>
						<li>Keep the warning context in mind when comparing sources.</li>
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
			</CardContent>
		</Card>
	);
}
