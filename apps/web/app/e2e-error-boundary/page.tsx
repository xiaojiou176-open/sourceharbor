"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";

export default function E2EErrorBoundaryPage() {
	const [shouldThrow, setShouldThrow] = useState(false);

	if (shouldThrow) {
		throw new Error("E2E_ROUTE_ERROR");
	}

	return (
		<main className="mx-auto flex min-h-[40vh] max-w-xl items-center justify-center px-4 py-10">
			<Button type="button" onClick={() => setShouldThrow(true)}>
				触发错误边界
			</Button>
		</main>
	);
}
