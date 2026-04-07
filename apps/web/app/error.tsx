"use client";

import { ErrorStateCard } from "@/components/error-state-card";

type RouteErrorProps = {
	error: Error & { digest?: string };
	reset: () => void;
};

export default function RouteError({ error, reset }: RouteErrorProps) {
	return (
		<section className="error-boundary-panel mx-auto flex min-h-[55vh] w-full max-w-xl items-center px-4 py-10">
			<ErrorStateCard
				eyebrow="Page error"
				title="Unable to load this page"
				titleAs="h2"
				description="Something unexpected happened. Retry or refresh the page."
				digest={error.digest}
				onRetry={reset}
			/>
		</section>
	);
}
