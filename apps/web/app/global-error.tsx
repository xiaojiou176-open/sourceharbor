"use client";

import { ErrorStateCard } from "@/components/error-state-card";

type GlobalErrorProps = {
	error: Error & { digest?: string };
	reset: () => void;
};

export default function GlobalError({ error, reset }: GlobalErrorProps) {
	return (
		<html lang="en">
			<body className="min-h-screen bg-background text-foreground">
				<main className="global-error-shell mx-auto flex min-h-screen w-full max-w-xl items-center px-4 py-10">
					<ErrorStateCard
						eyebrow="System error"
						title="The application hit an error"
						titleAs="h1"
						description="A system error occurred. Retry or refresh the page."
						digest={error.digest}
						onRetry={reset}
						className="folo-surface w-full border-destructive/35 bg-destructive/5"
					/>
				</main>
			</body>
		</html>
	);
}
