import type { ReaderDocument } from "@sourceharbor/sdk";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type SourceContributionDrawerProps = {
	document: ReaderDocument;
};

export function SourceContributionDrawer({
	document,
}: SourceContributionDrawerProps) {
	return (
		<Card className="border-border/70">
			<CardHeader className="pb-3">
				<CardTitle className="text-base">Source contribution drawer</CardTitle>
			</CardHeader>
			<CardContent className="space-y-4">
				<details
					className="rounded-xl border border-border/70 bg-background/80 p-4"
					open
				>
					<summary className="cursor-pointer font-medium">
						{document.source_refs.length} linked source items
					</summary>
					<div className="mt-4 space-y-4">
						{document.source_refs.map((source) => {
							const title =
								typeof source.title === "string" && source.title.trim()
									? source.title
									: "Untitled source";
							const jobBundleRoute =
								typeof source.job_bundle_route === "string"
									? source.job_bundle_route
									: null;
							const sourceUrl =
								typeof source.source_url === "string"
									? source.source_url
									: null;
							const digestPreview =
								typeof source.digest_preview === "string"
									? source.digest_preview
									: null;
							return (
								<div
									key={String(source.source_item_id ?? title)}
									className="rounded-lg border border-border/60 p-3"
								>
									<div className="flex flex-wrap items-center gap-2">
										<p className="font-medium">{title}</p>
										{typeof source.platform === "string" ? (
											<Badge variant="secondary">{source.platform}</Badge>
										) : null}
										{typeof source.source_origin === "string" ? (
											<Badge variant="outline">{source.source_origin}</Badge>
										) : null}
									</div>
									{digestPreview ? (
										<p className="mt-2 text-sm text-muted-foreground">
											{digestPreview}
										</p>
									) : null}
									<div className="mt-3 flex flex-wrap gap-3 text-sm">
										{sourceUrl ? (
											<a
												className="underline underline-offset-4"
												href={sourceUrl}
												target="_blank"
												rel="noreferrer"
											>
												Open source
											</a>
										) : null}
										{jobBundleRoute ? (
											<Link
												href={jobBundleRoute}
												className="underline underline-offset-4"
											>
												Open job bundle
											</Link>
										) : null}
									</div>
								</div>
							);
						})}
					</div>
				</details>
				<details className="rounded-xl border border-border/70 bg-background/80 p-4">
					<summary className="cursor-pointer font-medium">
						Section traceability
					</summary>
					<div className="mt-4 space-y-3 text-sm">
						{document.sections.map((section) => (
							<div
								key={section.section_id}
								className="rounded-lg border border-border/60 p-3"
							>
								<p className="font-medium">{section.title}</p>
								<p className="mt-1 text-muted-foreground">
									Section id: {section.section_id}
								</p>
								<p className="mt-2 text-muted-foreground">
									Linked source items:{" "}
									{section.source_item_ids.length
										? section.source_item_ids.join(", ")
										: "none"}
								</p>
							</div>
						))}
					</div>
				</details>
			</CardContent>
		</Card>
	);
}
