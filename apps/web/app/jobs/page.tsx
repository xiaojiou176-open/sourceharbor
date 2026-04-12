import type { Metadata } from "next";
import Link from "next/link";

import { getFlashMessage, toErrorCode } from "@/app/flash-message";
import { toDisplayStatus } from "@/app/status";
import { FormInputField } from "@/components/form-field";
import { mapStatusCssToTone, StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { apiClient } from "@/lib/api/client";
import { buildArtifactAssetUrl } from "@/lib/api/url";
import { formatDateTime, formatDateTimeWithSeconds } from "@/lib/format";
import { getLocaleMessages } from "@/lib/i18n/messages";
import {
	resolveSearchParams,
	type SearchParamsInput,
} from "@/lib/search-params";
import { buildProductMetadata } from "@/lib/seo";

const jobsCopy = getLocaleMessages().jobsPage;
const briefingsCopy = getLocaleMessages().briefingsPage;

export const metadata: Metadata = buildProductMetadata({
	title: jobsCopy.metadataTitle,
	description: jobsCopy.metadataDescription,
	route: "jobs",
});

type JobsPageProps = { searchParams?: SearchParamsInput };

function JobStatusBadge({ status }: { status: string }) {
	const statusDisplay = toDisplayStatus(status);
	return (
		<StatusBadge
			label={statusDisplay.label}
			tone={mapStatusCssToTone(statusDisplay.css)}
		/>
	);
}

export default async function JobsPage({ searchParams }: JobsPageProps) {
	const copy = getLocaleMessages().jobsPage;
	const { job_id: jobId } = await resolveSearchParams(searchParams, [
		"job_id",
	] as const);
	const retryHref = jobId
		? `/jobs?job_id=${encodeURIComponent(jobId)}`
		: "/jobs";

	let error: string | null = null;
	let job: Awaited<ReturnType<typeof apiClient.getJob>> | null = null;
	let jobCompare: Awaited<ReturnType<typeof apiClient.getJobCompare>> | null =
		null;
	let knowledgeCards: Awaited<
		ReturnType<typeof apiClient.getJobKnowledgeCards>
	> = [];
	if (jobId) {
		try {
			job = await apiClient.getJob(jobId);
		} catch (err) {
			error = getFlashMessage(toErrorCode(err));
		}
		if (!error) {
			try {
				jobCompare = await apiClient.getJobCompare(jobId);
			} catch {
				jobCompare = null;
			}
			try {
				knowledgeCards = await apiClient.getJobKnowledgeCards(jobId);
			} catch {
				knowledgeCards = [];
			}
		}
	}
	const jobStatus = job ? toDisplayStatus(job.status) : null;
	const pipelineStatus = job?.pipeline_final_status
		? toDisplayStatus(job.pipeline_final_status)
		: null;

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
					<h2 className="text-xl font-semibold">{copy.findTitle}</h2>
					<CardDescription>
						{copy.findDescriptionPrefix}{" "}
						<Link href="/">{copy.homeLinkLabel}</Link>{" "}
						{copy.findDescriptionConnector}{" "}
						<Link href="/feed">{copy.digestFeedLinkLabel}</Link>
						{copy.findDescriptionSuffix}
					</CardDescription>
				</CardHeader>
				<CardContent>
					<form
						method="GET"
						className="flex flex-wrap items-end gap-3"
						data-auto-disable-required="true"
					>
						<FormInputField
							id="job-id-field"
							name="job_id"
							label={copy.jobIdLabel}
							type="text"
							placeholder={copy.jobIdPlaceholder}
							defaultValue={jobId}
							required
							data-field-kind="identifier"
							fieldClassName="min-w-[280px] flex-1"
						/>
						<Button type="submit" data-interaction="control">
							{copy.searchButton}
						</Button>
					</form>
				</CardContent>
			</Card>

			{error ? (
				<Card
					className="folo-surface border-destructive/40 bg-destructive/5"
					role="alert"
					aria-live="assertive"
				>
					<CardHeader className="gap-2">
						<CardTitle className="text-base">
							{copy.lookupFailedTitle}
						</CardTitle>
						<CardDescription>{error}</CardDescription>
					</CardHeader>
					<CardContent className="pt-0">
						<Button asChild variant="outline" size="sm">
							<Link href={retryHref}>{copy.retryCurrentPageButton}</Link>
						</Button>
					</CardContent>
				</Card>
			) : null}

			{job ? (
				<>
					<output
						className="text-sm text-muted-foreground"
						aria-live="polite"
						aria-atomic="true"
					>
						{copy.currentStatusPrefix}: {jobStatus?.label ?? "-"},{" "}
						{copy.pipelineStatusPrefix}: {pipelineStatus?.label ?? "-"}, across{" "}
						{job.step_summary.length} {copy.acrossStepsSuffix}.
					</output>
					<section>
						<Card className="folo-surface border-border/70">
							<CardHeader>
								<h2 className="text-xl font-semibold">
									{copy.jobOverviewTitle}
								</h2>
							</CardHeader>
							<CardContent className="space-y-4">
								<dl className="grid gap-3 sm:grid-cols-2">
									<div className="space-y-1 rounded-lg border border-border/60 bg-muted/20 p-3">
										<dt className="text-xs uppercase tracking-wide text-muted-foreground">
											{copy.overviewFields.jobId}
										</dt>
										<dd className="break-all text-sm font-medium">{job.id}</dd>
									</div>
									<div className="space-y-1 rounded-lg border border-border/60 bg-muted/20 p-3">
										<dt className="text-xs uppercase tracking-wide text-muted-foreground">
											{copy.overviewFields.videoId}
										</dt>
										<dd className="break-all text-sm font-medium">
											{job.video_id}
										</dd>
									</div>
									<div className="space-y-1 rounded-lg border border-border/60 bg-muted/20 p-3">
										<dt className="text-xs uppercase tracking-wide text-muted-foreground">
											{copy.overviewFields.status}
										</dt>
										<dd>
											<JobStatusBadge status={jobStatus?.css ?? "queued"} />
										</dd>
									</div>
									<div className="space-y-1 rounded-lg border border-border/60 bg-muted/20 p-3">
										<dt className="text-xs uppercase tracking-wide text-muted-foreground">
											{copy.overviewFields.finalPipelineStatus}
										</dt>
										<dd>
											{pipelineStatus ? (
												<JobStatusBadge status={pipelineStatus.css} />
											) : (
												"-"
											)}
										</dd>
									</div>
									<div className="space-y-1 rounded-lg border border-border/60 bg-muted/20 p-3">
										<dt className="text-xs uppercase tracking-wide text-muted-foreground">
											{copy.overviewFields.createdAt}
										</dt>
										<dd className="text-sm">
											{formatDateTime(job.created_at)}
										</dd>
									</div>
									<div className="space-y-1 rounded-lg border border-border/60 bg-muted/20 p-3">
										<dt className="text-xs uppercase tracking-wide text-muted-foreground">
											{copy.overviewFields.updatedAt}
										</dt>
										<dd className="text-sm">
											{formatDateTime(job.updated_at)}
										</dd>
									</div>
								</dl>
								<Button
									asChild
									variant="link"
									size="sm"
									className="h-auto px-0"
								>
									<Link href={`/feed?item=${encodeURIComponent(job.id)}`}>
										{copy.viewInDigestFeed}
									</Link>
								</Button>
								<Button
									asChild
									variant="link"
									size="sm"
									className="h-auto px-0"
								>
									<a href={`/api/v1/jobs/${encodeURIComponent(job.id)}/bundle`}>
										{copy.downloadEvidenceBundle}
									</a>
								</Button>
								<Button
									asChild
									variant="link"
									size="sm"
									className="h-auto px-0"
								>
									<Link href="/briefings">
										{briefingsCopy.openBriefingButton}
									</Link>
								</Button>
								<p className="text-sm text-muted-foreground">
									{copy.evidenceBundleNote}
								</p>
							</CardContent>
						</Card>
					</section>

					<section>
						<Card className="folo-surface border-border/70">
							<CardHeader>
								<h2 className="text-xl font-semibold">
									{copy.stepSummaryTitle}
								</h2>
							</CardHeader>
							<CardContent>
								{job.step_summary.length === 0 ? (
									<p className="text-sm text-muted-foreground">
										{copy.stepSummaryEmpty}
									</p>
								) : (
									<div className="table-scroll overflow-x-auto rounded-lg border border-border/70">
										<table className="min-w-[720px] w-full text-sm">
											<caption className="sr-only">
												{copy.stepSummaryCaption}
											</caption>
											<thead className="bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
												<tr>
													<th scope="col" className="px-4 py-3 font-medium">
														{copy.stepSummaryHeaders.step}
													</th>
													<th scope="col" className="px-4 py-3 font-medium">
														{copy.stepSummaryHeaders.status}
													</th>
													<th scope="col" className="px-4 py-3 font-medium">
														{copy.stepSummaryHeaders.retries}
													</th>
													<th scope="col" className="px-4 py-3 font-medium">
														{copy.stepSummaryHeaders.startedAt}
													</th>
													<th scope="col" className="px-4 py-3 font-medium">
														{copy.stepSummaryHeaders.finishedAt}
													</th>
												</tr>
											</thead>
											<tbody>
												{job.step_summary.map((step, index) => (
													<tr
														key={`${step.name}-${index}`}
														className="border-t border-border/60"
													>
														<td className="px-4 py-3">{step.name}</td>
														<td className="px-4 py-3">
															<JobStatusBadge status={step.status} />
														</td>
														<td className="px-4 py-3">{step.attempt}</td>
														<td className="px-4 py-3">
															{formatDateTimeWithSeconds(step.started_at)}
														</td>
														<td className="px-4 py-3">
															{formatDateTimeWithSeconds(step.finished_at)}
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

					<section className="grid gap-4 lg:grid-cols-2">
						<Card className="folo-surface border-border/70">
							<CardHeader>
								<h2 className="text-xl font-semibold">{copy.compareTitle}</h2>
								<CardDescription>{copy.compareDescription}</CardDescription>
							</CardHeader>
							<CardContent className="space-y-3">
								{jobCompare?.has_previous ? (
									<>
										<dl className="grid gap-3 sm:grid-cols-3">
											<div className="space-y-1 rounded-lg border border-border/60 bg-muted/20 p-3">
												<dt className="text-xs uppercase tracking-wide text-muted-foreground">
													{copy.compareFields.previousJob}
												</dt>
												<dd className="break-all text-sm font-medium">
													{jobCompare.previous_job_id}
												</dd>
											</div>
											<div className="space-y-1 rounded-lg border border-border/60 bg-muted/20 p-3">
												<dt className="text-xs uppercase tracking-wide text-muted-foreground">
													{copy.compareFields.addedLines}
												</dt>
												<dd className="text-sm font-medium">
													{jobCompare.stats.added_lines}
												</dd>
											</div>
											<div className="space-y-1 rounded-lg border border-border/60 bg-muted/20 p-3">
												<dt className="text-xs uppercase tracking-wide text-muted-foreground">
													{copy.compareFields.removedLines}
												</dt>
												<dd className="text-sm font-medium">
													{jobCompare.stats.removed_lines}
												</dd>
											</div>
										</dl>
										{jobCompare.diff_markdown ? (
											<pre className="overflow-x-auto rounded-lg border border-border/70 bg-muted/20 p-3 text-xs leading-6">
												<code>{jobCompare.diff_markdown}</code>
											</pre>
										) : (
											<p className="text-sm text-muted-foreground">
												{copy.compareDiffEmpty}
											</p>
										)}
									</>
								) : (
									<p className="text-sm text-muted-foreground">
										{copy.compareEmpty}
									</p>
								)}
							</CardContent>
						</Card>

						<Card className="folo-surface border-border/70">
							<CardHeader>
								<h2 className="text-xl font-semibold">{copy.knowledgeTitle}</h2>
								<CardDescription>{copy.knowledgeDescription}</CardDescription>
							</CardHeader>
							<CardContent>
								{knowledgeCards.length === 0 ? (
									<p className="text-sm text-muted-foreground">
										{copy.knowledgeEmpty}
									</p>
								) : (
									<ul className="space-y-3 text-sm">
										{knowledgeCards.map((card) => (
											<li
												key={`${card.card_type}-${card.order_index}-${card.title}`}
												className="rounded-lg border border-border/60 bg-muted/20 p-3"
											>
												<p className="text-xs uppercase tracking-wide text-muted-foreground">
													{card.card_type} · {card.source_section}
												</p>
												<p className="mt-1 font-medium">{card.title}</p>
												<p className="mt-1 text-muted-foreground">
													{card.body}
												</p>
											</li>
										))}
									</ul>
								)}
							</CardContent>
						</Card>

						<Card className="folo-surface border-border/70">
							<CardHeader>
								<h2 className="text-xl font-semibold">
									{copy.degradationsTitle}
								</h2>
							</CardHeader>
							<CardContent>
								{job.degradations.length === 0 ? (
									<p className="text-sm text-muted-foreground">
										{copy.degradationsEmpty}
									</p>
								) : (
									<ul className="space-y-2 text-sm">
										{job.degradations.map((item, index) => {
											const degradationStatus =
												typeof item.status === "string"
													? toDisplayStatus(item.status).label
													: copy.naValue;
											return (
												<li
													key={`${item.step ?? "unknown"}-${index}`}
													className="leading-6"
												>
													<strong>{item.step ?? copy.unknownValue}</strong>:{" "}
													{item.reason ?? degradationStatus}
												</li>
											);
										})}
									</ul>
								)}
							</CardContent>
						</Card>

						<Card className="folo-surface border-border/70">
							<CardHeader>
								<h2 className="text-xl font-semibold">
									{copy.artifactIndexTitle}
								</h2>
							</CardHeader>
							<CardContent>
								{Object.keys(job.artifacts_index).length === 0 ? (
									<p className="text-sm text-muted-foreground">
										{copy.artifactsEmpty}
									</p>
								) : (
									<ul className="space-y-2 text-sm">
										{Object.entries(job.artifacts_index).map(([key, value]) => (
											<li key={key}>
												<strong>{key}</strong>:{" "}
												<a
													href={buildArtifactAssetUrl(job.id, value)}
													target="_blank"
													rel="noreferrer"
													className="text-primary underline-offset-4 hover:underline"
												>
													<code>{value}</code> {copy.opensInNewTabSuffix}
												</a>
											</li>
										))}
									</ul>
								)}
							</CardContent>
						</Card>
					</section>
				</>
			) : null}
		</div>
	);
}
