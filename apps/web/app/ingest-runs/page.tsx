import type { Metadata } from "next";
import Link from "next/link";

import { FormInputField } from "@/components/form-field";
import { mapStatusCssToTone, StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
} from "@/components/ui/card";
import { apiClient } from "@/lib/api/client";
import { formatDateTime } from "@/lib/format";
import { getLocaleMessages } from "@/lib/i18n/messages";
import {
	resolveSearchParams,
	type SearchParamsInput,
} from "@/lib/search-params";
import { buildProductMetadata } from "@/lib/seo";

const ingestRunsCopy = getLocaleMessages().ingestRunsPage;

export const metadata: Metadata = buildProductMetadata({
	title: ingestRunsCopy.metadataTitle,
	description: ingestRunsCopy.metadataDescription,
	route: "ingestRuns",
});

type IngestRunsPageProps = {
	searchParams?: SearchParamsInput;
};

function RunStatusBadge({ status }: { status: string }) {
	return <StatusBadge label={status} tone={mapStatusCssToTone(status)} />;
}

export default async function IngestRunsPage({
	searchParams,
}: IngestRunsPageProps) {
	const copy = getLocaleMessages().ingestRunsPage;
	const { run_id: runId } = await resolveSearchParams(searchParams, [
		"run_id",
	] as const);

	let runs: Awaited<ReturnType<typeof apiClient.listIngestRuns>> = [];
	let selectedRun: Awaited<ReturnType<typeof apiClient.getIngestRun>> | null =
		null;
	let error = false;

	try {
		runs = await apiClient.listIngestRuns({ limit: 10 });
		if (runId.trim()) {
			selectedRun = await apiClient.getIngestRun(runId.trim());
		}
	} catch {
		error = true;
	}

	return (
		<div className="folo-page-shell folo-unified-shell">
			<div className="folo-page-header">
				<p className="folo-page-kicker">{copy.kicker}</p>
				<h1 className="folo-page-title" data-route-heading tabIndex={-1}>
					{copy.heroTitle}
				</h1>
				<p className="folo-page-subtitle">{copy.heroSubtitle}</p>
			</div>

			<Card className="folo-surface border-border/70">
				<CardHeader>
					<h2 className="text-xl font-semibold">{copy.filterTitle}</h2>
					<CardDescription>{copy.filterDescription}</CardDescription>
				</CardHeader>
				<CardContent>
					<form method="GET" className="flex flex-wrap items-end gap-3">
						<FormInputField
							id="run-id-field"
							name="run_id"
							label={copy.runIdLabel}
							type="text"
							placeholder={copy.runIdPlaceholder}
							defaultValue={runId}
							data-field-kind="identifier"
							fieldClassName="min-w-[280px] flex-1"
						/>
						<Button type="submit">{copy.searchButton}</Button>
					</form>
				</CardContent>
			</Card>

			{error ? (
				<Card className="folo-surface border-destructive/40 bg-destructive/5">
					<CardHeader>
						<h2 className="text-xl font-semibold">{copy.loadErrorTitle}</h2>
						<CardDescription>{copy.loadErrorDescription}</CardDescription>
					</CardHeader>
				</Card>
			) : null}

			{!error ? (
				<section>
					<Card className="folo-surface border-border/70">
						<CardHeader className="flex flex-row items-start justify-between gap-4">
							<div className="space-y-2">
								<h2 className="text-xl font-semibold">{copy.sectionTitle}</h2>
								<CardDescription>{copy.sectionDescription}</CardDescription>
							</div>
						</CardHeader>
						<CardContent className="space-y-3">
							{runs.length === 0 ? (
								<p className="text-sm text-muted-foreground">{copy.empty}</p>
							) : (
								<div className="overflow-x-auto rounded-lg border border-border/70">
									<table className="min-w-[760px] w-full text-sm">
										<caption className="sr-only">{copy.sectionTitle}</caption>
										<thead className="bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
											<tr>
												<th scope="col" className="px-4 py-3 font-medium">
													Run ID
												</th>
												<th scope="col" className="px-4 py-3 font-medium">
													{copy.platform}
												</th>
												<th scope="col" className="px-4 py-3 font-medium">
													{copy.status}
												</th>
												<th scope="col" className="px-4 py-3 font-medium">
													{copy.jobs}
												</th>
												<th scope="col" className="px-4 py-3 font-medium">
													{copy.candidates}
												</th>
												<th scope="col" className="px-4 py-3 font-medium">
													{copy.created}
												</th>
											</tr>
										</thead>
										<tbody>
											{runs.map((run) => (
												<tr key={run.id} className="border-t border-border/60">
													<td className="px-4 py-3 font-mono text-xs">
														<Link
															href={`/ingest-runs?run_id=${encodeURIComponent(run.id)}`}
															className="text-primary underline-offset-4 hover:underline"
														>
															{run.id}
														</Link>
													</td>
													<td className="px-4 py-3">
														{run.platform ?? copy.allPlatforms}
													</td>
													<td className="px-4 py-3">
														<RunStatusBadge status={run.status} />
													</td>
													<td className="px-4 py-3">{run.jobs_created}</td>
													<td className="px-4 py-3">{run.candidates_count}</td>
													<td className="px-4 py-3">
														{formatDateTime(run.created_at)}
													</td>
												</tr>
											))}
										</tbody>
									</table>
								</div>
							)}
						</CardContent>
					</Card>
				</section>
			) : null}

			{selectedRun ? (
				<section>
					<Card className="folo-surface border-border/70">
						<CardHeader>
							<h2 className="text-xl font-semibold">{copy.detailTitle}</h2>
							<CardDescription>{copy.detailDescription}</CardDescription>
						</CardHeader>
						<CardContent className="space-y-4">
							<dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
								<div className="space-y-1 rounded-lg border border-border/60 bg-muted/20 p-3">
									<dt className="text-xs uppercase tracking-wide text-muted-foreground">
										{copy.detailFields.runId}
									</dt>
									<dd className="break-all text-sm font-medium">
										{selectedRun.id}
									</dd>
								</div>
								<div className="space-y-1 rounded-lg border border-border/60 bg-muted/20 p-3">
									<dt className="text-xs uppercase tracking-wide text-muted-foreground">
										{copy.detailFields.workflow}
									</dt>
									<dd className="break-all text-sm font-medium">
										{selectedRun.workflow_id ?? "-"}
									</dd>
								</div>
								<div className="space-y-1 rounded-lg border border-border/60 bg-muted/20 p-3">
									<dt className="text-xs uppercase tracking-wide text-muted-foreground">
										{copy.detailFields.jobsCreated}
									</dt>
									<dd className="text-sm font-medium">
										{selectedRun.jobs_created}
									</dd>
								</div>
								<div className="space-y-1 rounded-lg border border-border/60 bg-muted/20 p-3">
									<dt className="text-xs uppercase tracking-wide text-muted-foreground">
										{copy.detailFields.candidates}
									</dt>
									<dd className="text-sm font-medium">
										{selectedRun.candidates_count}
									</dd>
								</div>
							</dl>
							{selectedRun.items.length > 0 ? (
								<div className="overflow-x-auto rounded-lg border border-border/70">
									<table className="min-w-[760px] w-full text-sm">
										<caption className="sr-only">
											{copy.itemsTableCaption}
										</caption>
										<thead className="bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
											<tr>
												<th scope="col" className="px-4 py-3 font-medium">
													{copy.itemsTableHeaders.videoUid}
												</th>
												<th scope="col" className="px-4 py-3 font-medium">
													{copy.itemsTableHeaders.title}
												</th>
												<th scope="col" className="px-4 py-3 font-medium">
													{copy.itemsTableHeaders.job}
												</th>
												<th scope="col" className="px-4 py-3 font-medium">
													{copy.itemsTableHeaders.type}
												</th>
												<th scope="col" className="px-4 py-3 font-medium">
													{copy.itemsTableHeaders.status}
												</th>
											</tr>
										</thead>
										<tbody>
											{selectedRun.items.map((item) => (
												<tr key={item.id} className="border-t border-border/60">
													<td className="px-4 py-3 font-mono text-xs">
														{item.video_uid}
													</td>
													<td className="px-4 py-3">{item.title ?? "-"}</td>
													<td className="px-4 py-3">
														{item.job_id ? (
															<Link
																href={`/jobs?job_id=${encodeURIComponent(item.job_id)}`}
																className="text-primary underline-offset-4 hover:underline"
															>
																{item.job_id}
															</Link>
														) : (
															"-"
														)}
													</td>
													<td className="px-4 py-3">{item.content_type}</td>
													<td className="px-4 py-3">{item.item_status}</td>
												</tr>
											))}
										</tbody>
									</table>
								</div>
							) : (
								<p className="text-sm text-muted-foreground">
									{copy.detailEmpty}
								</p>
							)}
						</CardContent>
					</Card>
				</section>
			) : null}
		</div>
	);
}
