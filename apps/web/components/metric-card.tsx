"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type MetricCardProps = {
	label: string;
	value: React.ReactNode;
	description?: React.ReactNode;
	cta?: React.ReactNode;
	accent?: "warning" | "error";
};

export function MetricCard({
	label,
	value,
	description,
	cta,
	accent,
}: MetricCardProps) {
	return (
		<Card className="folo-surface folo-metric-card" data-accent={accent}>
			<CardHeader className="gap-2 pb-0">
				<CardTitle className="text-xs uppercase tracking-[0.12em] text-muted-foreground">
					{label}
				</CardTitle>
			</CardHeader>
			<CardContent className="pt-3">
				<div className="metric-value">{value}</div>
				{description ? (
					<div className="mt-2 text-sm text-muted-foreground">
						{description}
					</div>
				) : null}
				{cta ? <div className="mt-4">{cta}</div> : null}
			</CardContent>
		</Card>
	);
}
