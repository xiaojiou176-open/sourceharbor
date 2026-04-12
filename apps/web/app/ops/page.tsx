import type { Metadata } from "next";
import Link from "next/link";

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
import type { OpsGate, OpsInboxItem, OpsInboxResponse } from "@/lib/api/types";
import { formatDateTime } from "@/lib/format";
import { getLocaleMessages } from "@/lib/i18n/messages";
import { buildProductMetadata } from "@/lib/seo";

const opsCopy = getLocaleMessages().ops;

export const metadata: Metadata = buildProductMetadata({
	title: opsCopy.metadataTitle,
	description: opsCopy.metadataDescription,
	route: "ops",
});

function toBadgeStatus(status: string): string {
	const normalized = status.trim().toLowerCase();
	if (normalized === "critical") {
		return "failed";
	}
	if (normalized === "warning") {
		return "queued";
	}
	if (
		normalized === "ready" ||
		normalized === "ok" ||
		normalized === "healthy"
	) {
		return "succeeded";
	}
	if (
		normalized === "warn" ||
		normalized === "queued" ||
		normalized === "timeout_or_unknown"
	) {
		return "queued";
	}
	if (
		normalized === "blocked" ||
		normalized === "failed" ||
		normalized === "unavailable"
	) {
		return "failed";
	}
	if (normalized === "degraded") {
		return "degraded";
	}
	return "queued";
}

function ReadinessBadge({ label, status }: { label: string; status: string }) {
	return (
		<StatusBadge
			label={label}
			tone={mapStatusCssToTone(toBadgeStatus(status))}
		/>
	);
}

function SummaryCard({
	title,
	value,
	description,
	status,
}: {
	title: string;
	value: number;
	description: string;
	status: string;
}) {
	const className =
		status === "blocked"
			? "folo-surface border-destructive/40 bg-destructive/5"
			: status === "warn"
				? "folo-surface border-amber-300/70 bg-amber-50/40 dark:border-amber-900 dark:bg-amber-950/15"
				: "folo-surface border-border/70";

	return (
		<Card className={className}>
			<CardHeader className="gap-2">
				<CardDescription>{title}</CardDescription>
				<div className="text-3xl font-semibold">{value}</div>
			</CardHeader>
			<CardContent className="pt-0 text-sm text-muted-foreground">
				{description}
			</CardContent>
		</Card>
	);
}

function buildSummaryStatus(value: number): string {
	return value > 0 ? "blocked" : "ready";
}

function GateCard({ title, gate }: { title: string; gate: OpsGate }) {
	return (
		<Card className="folo-surface border-border/70">
			<CardHeader className="gap-2">
				<div className="flex items-center justify-between gap-3">
					<CardTitle className="text-base">{title}</CardTitle>
					<ReadinessBadge label={gate.status} status={gate.status} />
				</div>
				<CardDescription>{gate.summary}</CardDescription>
			</CardHeader>
			<CardContent className="space-y-2 text-sm text-muted-foreground">
				<p>{gate.next_step}</p>
			</CardContent>
		</Card>
	);
}

function InboxRow({ item }: { item: OpsInboxItem }) {
	return (
		<tr className="border-t border-border/60">
			<td className="px-4 py-3 align-top">{item.kind}</td>
			<td className="px-4 py-3 align-top">
				<div className="space-y-1">
					<p className="font-medium">{item.title}</p>
					<p className="text-muted-foreground">{item.detail}</p>
				</div>
			</td>
			<td className="px-4 py-3 align-top">
				<ReadinessBadge label={item.status_label} status={item.severity} />
			</td>
			<td className="px-4 py-3 align-top text-sm text-muted-foreground">
				{formatDateTime(item.last_seen_at) || "-"}
			</td>
			<td className="px-4 py-3 align-top">
				<Button asChild variant="link" size="sm" className="h-auto px-0">
					<Link href={item.href}>{item.action_label} →</Link>
				</Button>
			</td>
		</tr>
	);
}

const SITE_CAPABILITY_ITEMS = [
	{
		site: "Google Account",
		layer: "DOM / page-state proof",
		role: "Login-persistence and repo-owned Chrome sanity anchor",
		boundary: "Keep this as a proof anchor, not an account-automation target.",
	},
	{
		site: "YouTube",
		layer: "Hybrid: Data API + DOM proof",
		role: "Strongest source lane today with the deepest diagnostics and read-only proof.",
		boundary:
			"Full live receipt still depends on operator-managed API access and local login state.",
	},
	{
		site: "Bilibili",
		layer: "DOM today, hybrid later",
		role: "Account-proof anchor for the strong-supported video lane.",
		boundary:
			"Human login still gates stronger proof, and account-side writes stay out of scope.",
	},
	{
		site: "Resend",
		layer: "Admin UI + provider configuration",
		role: "Operator proof surface for notifications, not a content-ingestion source.",
		boundary:
			"Sender/domain/mailbox setup still remains an external provider-admin action.",
	},
	{
		site: "RSSHub / generic RSS",
		layer: "HTTP / API substrate",
		role: "Most complete source-universe adapter layer in code today.",
		boundary:
			"Route quality still needs route-by-route proof instead of a blanket claim.",
	},
] as const;

type OpsNextStep = {
	title: string;
	detail: string;
	href: string;
	actionLabel: string;
	status: string;
};

function buildNextSteps(
	payload: OpsInboxResponse,
	copy: ReturnType<typeof getLocaleMessages>["ops"],
): OpsNextStep[] {
	const steps: OpsNextStep[] = [];
	const pushStep = (step: OpsNextStep) => {
		if (
			steps.some(
				(existing) =>
					existing.title === step.title && existing.href === step.href,
			)
		) {
			return;
		}
		steps.push(step);
	};

	const gateActions: Array<{
		key: keyof OpsInboxResponse["gates"];
		title: string;
		href: string;
		actionLabel: string;
	}> = [
		{
			key: "notifications",
			title: "Notifications",
			href: "/settings",
			actionLabel: "Open settings",
		},
		{
			key: "disk_governance",
			title: "Disk governance",
			href: "/ops#hardening-gates",
			actionLabel: copy.nextSteps.openAction,
		},
		{
			key: "retrieval",
			title: "Retrieval",
			href: "/search",
			actionLabel: "Open Search",
		},
		{
			key: "ui_audit",
			title: "UI audit",
			href: "/ops#hardening-gates",
			actionLabel: copy.nextSteps.openAction,
		},
		{
			key: "computer_use",
			title: "Computer use",
			href: "/ops#hardening-gates",
			actionLabel: copy.nextSteps.openAction,
		},
	];

	for (const gateAction of gateActions) {
		const gate = payload.gates[gateAction.key];
		if (gate.status === "ready" || gate.status === "ok") {
			continue;
		}
		pushStep({
			title: `${copy.nextSteps.gatePrefix}: ${gateAction.title}`,
			detail: gate.next_step || gate.summary,
			href: gateAction.href,
			actionLabel: gateAction.actionLabel,
			status: gate.status,
		});
	}

	for (const item of payload.inbox_items.slice(0, 2)) {
		pushStep({
			title: `${copy.nextSteps.triagePrefix}: ${item.title}`,
			detail: item.detail,
			href: item.href,
			actionLabel: item.action_label,
			status: item.severity,
		});
	}

	return steps.slice(0, 4);
}

export default async function OpsPage() {
	const copy = getLocaleMessages().ops;
	const payload = await apiClient
		.getOpsInbox({ limit: 6, window_hours: 24 })
		.catch(() => null);

	if (payload === null) {
		return (
			<div className="folo-page-shell folo-unified-shell">
				<div className="folo-page-header">
					<p className="folo-page-kicker">{copy.kicker}</p>
					<h1 className="folo-page-title" data-route-heading tabIndex={-1}>
						{copy.heroTitle}
					</h1>
					<p className="folo-page-subtitle">{copy.heroSubtitle}</p>
				</div>
				<Card className="folo-surface border-destructive/40 bg-destructive/5">
					<CardHeader className="gap-2">
						<CardTitle className="text-base">{copy.loadErrorTitle}</CardTitle>
						<CardDescription>{copy.loadErrorDescription}</CardDescription>
					</CardHeader>
					<CardContent className="pt-0">
						<Button asChild variant="outline" size="sm">
							<Link href="/">{copy.backToDashboard}</Link>
						</Button>
					</CardContent>
				</Card>
			</div>
		);
	}

	const providerIssues = payload.provider_health.providers.filter(
		(provider) => {
			const status = String(provider.last_status || "").toLowerCase();
			return status === "warn" || status === "fail";
		},
	);
	const nextSteps = buildNextSteps(payload, copy);

	return (
		<div className="folo-page-shell folo-unified-shell">
			<div className="folo-page-header">
				<p className="folo-page-kicker">{copy.kicker}</p>
				<h1 className="folo-page-title" data-route-heading tabIndex={-1}>
					{copy.heroTitle}
				</h1>
				<p className="folo-page-subtitle">{copy.heroSubtitle}</p>
			</div>

			{payload.failed_jobs.status !== "ok" ||
			payload.failed_ingest_runs.status !== "ok" ||
			payload.notification_deliveries.status !== "ok" ? (
				<Card className="folo-surface border-amber-300/70 bg-amber-50/40 dark:border-amber-900 dark:bg-amber-950/15">
					<CardHeader className="gap-2">
						<CardTitle className="text-base">{copy.partialDataTitle}</CardTitle>
						<CardDescription>{copy.partialDataDescription}</CardDescription>
					</CardHeader>
					<CardContent className="pt-0">
						<Button asChild variant="outline" size="sm">
							<Link href="/">{copy.backToDashboard}</Link>
						</Button>
					</CardContent>
				</Card>
			) : null}

			<section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
				<SummaryCard
					title={copy.summary.attentionItems.title}
					value={payload.overview.attention_items}
					description={copy.summary.attentionItems.description}
					status={buildSummaryStatus(payload.overview.attention_items)}
				/>
				<SummaryCard
					title={copy.summary.failedJobs.title}
					value={payload.overview.failed_jobs}
					description={copy.summary.failedJobs.description}
					status={buildSummaryStatus(payload.overview.failed_jobs)}
				/>
				<SummaryCard
					title={copy.summary.failedIngest.title}
					value={payload.overview.failed_ingest_runs}
					description={copy.summary.failedIngest.description}
					status={buildSummaryStatus(payload.overview.failed_ingest_runs)}
				/>
				<SummaryCard
					title={copy.summary.notificationGate.title}
					value={payload.overview.notification_or_gate_issues}
					description={copy.summary.notificationGate.description}
					status={buildSummaryStatus(
						payload.overview.notification_or_gate_issues,
					)}
				/>
			</section>

			<section id="ops-inbox">
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<CardTitle>{copy.inbox.title}</CardTitle>
						<CardDescription>{copy.inbox.description}</CardDescription>
					</CardHeader>
					<CardContent className="space-y-3">
						{payload.inbox_items.length === 0 ? (
							<p className="text-sm text-muted-foreground">
								{copy.inbox.empty}
							</p>
						) : (
							<div className="overflow-x-auto rounded-lg border border-border/70">
								<table className="min-w-[840px] w-full text-sm">
									<caption className="sr-only">Ops inbox</caption>
									<thead className="bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
										<tr>
											<th scope="col" className="px-4 py-3 font-medium">
												Type
											</th>
											<th scope="col" className="px-4 py-3 font-medium">
												What happened
											</th>
											<th scope="col" className="px-4 py-3 font-medium">
												Current status
											</th>
											<th scope="col" className="px-4 py-3 font-medium">
												Last seen
											</th>
											<th scope="col" className="px-4 py-3 font-medium">
												Primary action
											</th>
										</tr>
									</thead>
									<tbody>
										{payload.inbox_items.map((item) => (
											<InboxRow
												key={`${item.kind}-${item.href}-${item.title}`}
												item={item}
											/>
										))}
									</tbody>
								</table>
							</div>
						)}
					</CardContent>
				</Card>
			</section>

			<section id="hardening-gates" className="grid gap-4 lg:grid-cols-2">
				<GateCard title="Retrieval" gate={payload.gates.retrieval} />
				<GateCard title="Notifications" gate={payload.gates.notifications} />
				<GateCard
					title="Disk governance"
					gate={payload.gates.disk_governance}
				/>
				<GateCard title="UI audit" gate={payload.gates.ui_audit} />
				<GateCard title="Computer use" gate={payload.gates.computer_use} />
			</section>

			<section>
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<CardTitle>{copy.nextSteps.title}</CardTitle>
						<CardDescription>{copy.nextSteps.description}</CardDescription>
					</CardHeader>
					<CardContent className="space-y-3 text-sm text-muted-foreground">
						{nextSteps.length === 0 ? (
							<p>{copy.nextSteps.noActions}</p>
						) : (
							<ul className="space-y-3">
								{nextSteps.map((step) => (
									<li
										key={`${step.title}-${step.href}`}
										className="rounded-lg border border-border/60 bg-muted/20 p-3"
									>
										<div className="flex items-center justify-between gap-3">
											<p className="font-medium text-foreground">
												{step.title}
											</p>
											<ReadinessBadge
												label={step.status}
												status={step.status}
											/>
										</div>
										<p>{step.detail}</p>
										<Button
											asChild
											variant="link"
											size="sm"
											className="mt-2 h-auto px-0"
										>
											<Link href={step.href}>{step.actionLabel} →</Link>
										</Button>
									</li>
								))}
							</ul>
						)}
					</CardContent>
				</Card>
			</section>

			<section id="site-capability-truth">
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<CardTitle>Site capability truth</CardTitle>
						<CardDescription>
							Use this as the shortest honest ledger for what the repo can
							already prove at the site level, what is still only local or
							operator proof, and where stronger claims still depend on an
							external step.
						</CardDescription>
					</CardHeader>
					<CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
						{SITE_CAPABILITY_ITEMS.map((item) => (
							<Card key={item.site} className="border-border/60">
								<CardHeader className="gap-2">
									<CardTitle className="text-base">{item.site}</CardTitle>
									<CardDescription>{item.layer}</CardDescription>
								</CardHeader>
								<CardContent className="space-y-2 pt-0 text-sm text-muted-foreground">
									<p>{item.role}</p>
									<p>{item.boundary}</p>
								</CardContent>
							</Card>
						))}
					</CardContent>
				</Card>
			</section>

			<section className="grid gap-4 lg:grid-cols-2">
				<Card id="provider-health" className="folo-surface border-border/70">
					<CardHeader>
						<CardTitle>{copy.providerHealth.title}</CardTitle>
						<CardDescription>{copy.providerHealth.description}</CardDescription>
					</CardHeader>
					<CardContent className="space-y-3">
						{providerIssues.length === 0 ? (
							<p className="text-sm text-muted-foreground">
								{copy.providerHealth.empty}
							</p>
						) : (
							<ul className="space-y-3 text-sm text-muted-foreground">
								{providerIssues.map((provider) => (
									<li
										key={provider.provider}
										className="rounded-lg border border-border/60 bg-muted/20 p-3"
									>
										<div className="flex items-center justify-between gap-3">
											<p className="font-medium text-foreground">
												{provider.provider}
											</p>
											<ReadinessBadge
												label={provider.last_status || "unknown"}
												status={provider.last_status || "warn"}
											/>
										</div>
										<p>
											{provider.last_message ||
												provider.last_error_kind ||
												copy.providerHealth.defaultMessage}
										</p>
									</li>
								))}
							</ul>
						)}
					</CardContent>
				</Card>

				<Card
					id="notification-readiness"
					className="folo-surface border-border/70"
				>
					<CardHeader>
						<CardTitle>{copy.notificationReadiness.title}</CardTitle>
						<CardDescription>
							{copy.notificationReadiness.description}
						</CardDescription>
					</CardHeader>
					<CardContent className="space-y-3 text-sm text-muted-foreground">
						<p>{payload.gates.notifications.summary}</p>
						<p>{payload.gates.notifications.next_step}</p>
						{payload.notification_deliveries.items.length === 0 ? (
							<p>{copy.notificationReadiness.empty}</p>
						) : (
							<ul className="space-y-2">
								{payload.notification_deliveries.items.map((item) => (
									<li
										key={item.id}
										className="rounded-lg border border-border/60 bg-muted/20 p-3"
									>
										<p className="font-medium text-foreground">{item.kind}</p>
										<p>
											{item.status}
											{item.error_message ? ` · ${item.error_message}` : ""}
										</p>
									</li>
								))}
							</ul>
						)}
					</CardContent>
				</Card>
			</section>
		</div>
	);
}
