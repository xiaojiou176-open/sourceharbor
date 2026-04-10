import { AlertTriangle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

type YellowWarningCardProps = {
	reasons: string[];
};

export function YellowWarningCard({ reasons }: YellowWarningCardProps) {
	return (
		<Card className="border-amber-300 bg-amber-50/90 text-amber-950 shadow-sm">
			<CardHeader className="space-y-3 pb-3">
				<div className="flex flex-wrap items-center gap-2">
					<Badge className="border-amber-400/80 bg-amber-100 text-amber-950 hover:bg-amber-100">
						Published with gap
					</Badge>
				</div>
				<h2 className="flex items-center gap-2 text-base font-semibold">
					<AlertTriangle className="h-4 w-4" />
					Yellow warning
				</h2>
			</CardHeader>
			<CardContent className="space-y-4 text-sm">
				<div className="space-y-1">
					<p className="font-medium">What this means</p>
					<p>
						This document is still readable, but one or more evidence lanes are
						missing or degraded. Treat the body as a useful reading unit, not as
						a fully sealed proof packet.
					</p>
				</div>
				<div className="space-y-1">
					<p className="font-medium">How to read safely</p>
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
