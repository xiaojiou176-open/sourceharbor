import type { ReaderDocument } from "@sourceharbor/sdk";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

type SourceContributionDrawerProps = {
	document: ReaderDocument;
};

export function SourceContributionDrawer({
	document,
}: SourceContributionDrawerProps) {
	const sourceCount = document.source_refs.length;
	const sectionCount = document.sections.length;
	const warningContext = document.published_with_gap
		? "Warning context available"
		: "Clear provenance map";

	return (
		<Card className="border-border/70 shadow-sm">
			<CardHeader className="space-y-2 pb-3">
				<h2 className="text-base font-semibold">Source contribution drawer</h2>
				<p className="text-sm text-muted-foreground">
					Keep the main body clean, then open the drawer only when you want to
					inspect where each claim came from.
				</p>
			</CardHeader>
			<CardContent className="space-y-4">
				<div className="flex flex-wrap gap-2 text-sm">
					<Badge variant="secondary">Sources {sourceCount}</Badge>
					<Badge variant="outline">Sections {sectionCount}</Badge>
					<Badge variant="outline">{warningContext}</Badge>
				</div>
				<p className="text-sm text-muted-foreground">
					Keep the body as the first reading pass. Open this drawer when you
					want to inspect which source items and sections back the current
					document.
				</p>
				<details className="rounded-xl border border-border/70 bg-background/80 p-4">
					<summary className="cursor-pointer font-medium">
						{sourceCount} linked source items
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
									className="rounded-xl border border-border/60 p-3"
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
										<p className="mt-2 line-clamp-2 text-sm text-muted-foreground">
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
								className="rounded-xl border border-border/60 p-3"
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
