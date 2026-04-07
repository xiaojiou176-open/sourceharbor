import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type LoadingStateCardProps = {
	title: string;
	message: string;
	messageId: string;
};

export function LoadingStateCard({
	title,
	message,
	messageId,
}: LoadingStateCardProps) {
	return (
		<section
			className="mx-auto flex min-h-[45vh] w-full max-w-2xl items-center px-4 py-8"
			aria-busy="true"
			aria-describedby={messageId}
		>
			<Card className="folo-surface w-full border-border/70">
				<CardHeader className="space-y-3">
					<CardTitle className="text-xl" aria-hidden="true">
						{title}
					</CardTitle>
					<div className="space-y-2" aria-hidden="true">
						<div className="skeleton-line skeleton-line--long h-3" />
						<div className="skeleton-line skeleton-line--medium h-3" />
						<div className="skeleton-line skeleton-line--short h-3" />
					</div>
				</CardHeader>
				<CardContent className="pt-0">
					<output
						id={messageId}
						aria-live="polite"
						aria-atomic="true"
						className="text-sm text-muted-foreground"
					>
						{message}
					</output>
				</CardContent>
			</Card>
		</section>
	);
}
