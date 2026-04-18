import type { ReaderDocument } from "@sourceharbor/sdk";
import { Braces, FileStack } from "lucide-react";
import Link from "next/link";

import { SourceIdentityCard } from "@/components/source-identity-card";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { editorialSans, editorialSerif } from "@/lib/editorial-fonts";
import { resolveReaderSourceIdentity } from "@/lib/source-identity";

type SourceContributionDrawerProps = {
	document: ReaderDocument;
};

function normalizeSectionTitle(title: string | null | undefined): string {
	const value = String(title || "").trim();
	if (!value) return "Supporting section";
	if (value.toLowerCase() === "source context") {
		return "Background context";
	}
	return value;
}

export function SourceContributionDrawer({
	document,
}: SourceContributionDrawerProps) {
	const sourceCount = document.source_refs.length;
	const sectionCount = document.sections.length;
	const warningContext = document.published_with_gap
		? "Warning context included"
		: "Provenance ready";
	const sourceIdentityById = new Map(
		document.source_refs.map((source) => [
			String(source.source_item_id),
			resolveReaderSourceIdentity(source),
		]),
	);

	return (
		<Card
			className={`border-border/70 bg-background/95 shadow-sm ${editorialSans.className}`}
		>
			<CardHeader className="space-y-3 pb-3">
				<div className="flex flex-wrap items-center gap-2">
					<Badge variant="secondary">Source notes</Badge>
					<Badge variant="outline">{warningContext}</Badge>
				</div>
				<div className="space-y-2">
					<h2 className={`text-base font-semibold ${editorialSerif.className}`}>
						Where this story came from
					</h2>
					<p className="text-sm leading-6 text-muted-foreground">
						Read the body first. Keep the warning in mind. Then open these notes
						only when you want the source list behind a section, quote, or
						warning.
					</p>
				</div>
			</CardHeader>
			<CardContent className="space-y-4">
				<div className="rounded-[1.4rem] border border-border/60 bg-muted/15 p-4">
					<div className="flex flex-wrap gap-2">
						<Badge variant="outline">{sourceCount} linked sources</Badge>
						<Badge variant="outline">{sectionCount} story sections</Badge>
					</div>
					<p className="mt-3 text-sm leading-6 text-muted-foreground">
						Open the source list when you want the original items. Open section
						support when you want to see which notes back a part of the story.
					</p>
				</div>
				<div className="rounded-2xl border border-border/70 bg-background/80 p-4">
					<div className="flex items-start justify-between gap-3">
						<div className="space-y-1.5">
							<p className="flex items-center gap-2 font-medium text-foreground">
								<FileStack className="h-4 w-4 text-rose-600" />
								Browse linked sources
							</p>
							<p className="text-sm leading-6 text-muted-foreground">
								Open the source list when you want the original items. The
								section support rail stays below for later.
							</p>
						</div>
						<span className="text-xs text-muted-foreground">
							{sourceCount} source notes
						</span>
					</div>
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
							const subscriptionRoute =
								typeof source.subscription_id === "string" &&
								source.subscription_id.trim()
									? `/feed?sub=${encodeURIComponent(source.subscription_id.trim())}`
									: null;
							const sourceUrl =
								typeof source.source_url === "string"
									? source.source_url
									: null;
							const digestPreview =
								typeof source.digest_preview === "string"
									? source.digest_preview
									: null;

							const identity = resolveReaderSourceIdentity(source);
							return (
								<SourceIdentityCard
									key={String(source.source_item_id ?? title)}
									identity={{
										...identity,
										description: digestPreview || identity.description,
									}}
									compact
									action={
										<div className="flex flex-wrap gap-3 text-sm">
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
											{subscriptionRoute ? (
												<Link
													href={subscriptionRoute}
													className="underline underline-offset-4"
												>
													Open tracked universe
												</Link>
											) : null}
										</div>
									}
								/>
							);
						})}
					</div>
				</div>
				<details className="rounded-2xl border border-border/70 bg-background/80 p-4">
					<summary className="m-[-0.5rem] cursor-pointer list-none rounded-xl p-2 transition-colors hover:bg-muted/30">
						<div className="flex items-start justify-between gap-3">
							<span className="flex items-center gap-2 font-medium text-foreground">
								<Braces className="h-4 w-4 text-rose-600" />
								See section support
							</span>
							<span className="text-xs text-muted-foreground">
								After the body
							</span>
						</div>
					</summary>
					<div className="mt-4 space-y-3 text-sm">
						{document.sections.map((section) => {
							const sourceTitles = section.source_item_ids
								.map(
									(sourceId) => sourceIdentityById.get(String(sourceId))?.title,
								)
								.filter(Boolean) as string[];
							return (
								<div
									key={section.section_id}
									className="rounded-xl border border-border/60 p-3"
								>
									<p className="font-medium">
										{normalizeSectionTitle(section.title)}
									</p>
									<p className="mt-1 text-muted-foreground">
										{sourceTitles.length
											? `Supported by ${sourceTitles.length} linked ${
													sourceTitles.length === 1 ? "source" : "sources"
												}.`
											: "No linked sources yet."}
									</p>
									{sourceTitles.length ? (
										<div className="mt-3 flex flex-wrap gap-1.5">
											{sourceTitles.map((label) => (
												<Badge
													key={`${section.section_id}-${label}`}
													variant="outline"
													className="border-border/55 bg-background/75 text-[10px] text-muted-foreground"
												>
													{label}
												</Badge>
											))}
										</div>
									) : null}
								</div>
							);
						})}
					</div>
				</details>
			</CardContent>
		</Card>
	);
}
