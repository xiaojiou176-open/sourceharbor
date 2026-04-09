import { AlertTriangle } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type YellowWarningCardProps = {
	reasons: string[];
};

export function YellowWarningCard({ reasons }: YellowWarningCardProps) {
	return (
		<Card className="border-amber-300 bg-amber-50/90 text-amber-950 shadow-sm">
			<CardHeader className="pb-3">
				<CardTitle className="flex items-center gap-2 text-base">
					<AlertTriangle className="h-4 w-4" />
					Yellow warning
				</CardTitle>
			</CardHeader>
			<CardContent className="space-y-2 text-sm">
				<p>
					This reader document stays readable, but some source evidence still
					carried degradations or missing digest output.
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
