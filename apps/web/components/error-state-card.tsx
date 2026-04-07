import type { ElementType } from "react";

import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
} from "@/components/ui/card";

type ErrorStateCardProps = {
	eyebrow: string;
	title: string;
	description: string;
	digest?: string;
	onRetry: () => void;
	className?: string;
	titleAs?: "h1" | "h2";
};

export function ErrorStateCard({
	eyebrow,
	title,
	description,
	digest,
	onRetry,
	className,
	titleAs = "h2",
}: ErrorStateCardProps) {
	const TitleTag = titleAs as ElementType;
	return (
		<Card
			className={
				className ??
				"folo-surface w-full border-destructive/35 bg-destructive/5"
			}
		>
			<CardHeader className="space-y-2">
				<p className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
					{eyebrow}
				</p>
				<TitleTag className="text-2xl font-semibold">{title}</TitleTag>
				<CardDescription role="alert" aria-live="assertive" aria-atomic="true">
					{description}
				</CardDescription>
				{digest ? (
					<p className="text-sm text-muted-foreground">
						Error code: <code>{digest}</code>
					</p>
				) : null}
			</CardHeader>
			<CardContent>
				<Button type="button" onClick={onRetry} data-interaction="control">
					Retry page
				</Button>
			</CardContent>
		</Card>
	);
}
