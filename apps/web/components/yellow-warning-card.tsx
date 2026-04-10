import { AlertTriangle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

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
				<CardTitle className="flex items-center gap-2 text-base">
					<AlertTriangle className="h-4 w-4" />
					Yellow warning
				</CardTitle>
			</CardHeader>
			<CardContent className="space-y-2 text-sm">
				<p>
					This reader document is still readable, but one or more source lanes
					still carry missing or degraded evidence. Read the main body first,
					then inspect the drawer before you reuse claims outside this surface.
				</p>
				<ul className="list-disc space-y-1 pl-5">
					{reasons.map((reason) => (
						<li key={reason}>{reason}</li>
					))}
				</ul>
			</CardContent>
		</Card>
	);
}
