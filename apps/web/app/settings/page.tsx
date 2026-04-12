import type { Metadata } from "next";
import Link from "next/link";

import { getActionSessionTokenForForm } from "@/app/action-security";
import { getFlashMessage } from "@/app/flash-message";
import {
	sendTestNotificationAction,
	updateNotificationConfigAction,
} from "@/app/settings/actions";
import {
	FormCheckboxField,
	FormField,
	FormFieldHint,
	FormFieldLabel,
	FormInputField,
} from "@/components/form-field";
import { SubmitButton } from "@/components/submit-button";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { WebActionSessionHiddenInput } from "@/components/web-action-session-hidden-input";
import { apiClient } from "@/lib/api/client";
import { formatDateTime } from "@/lib/format";
import { getLocaleMessages } from "@/lib/i18n/messages";
import {
	resolveSearchParams,
	type SearchParamsInput,
} from "@/lib/search-params";
import { buildProductMetadata } from "@/lib/seo";

const settingsCopy = getLocaleMessages().settings;

export const metadata: Metadata = buildProductMetadata({
	title: settingsCopy.metadataTitle,
	description: settingsCopy.metadataDescription,
	route: "settings",
});

type SettingsPageProps = {
	searchParams?: SearchParamsInput;
};

export default async function SettingsPage({
	searchParams,
}: SettingsPageProps) {
	const copy = getLocaleMessages().settings;
	const { status, code } = await resolveSearchParams(searchParams, [
		"status",
		"code",
	] as const);
	const sessionToken = getActionSessionTokenForForm();
	const configResult = await apiClient
		.getNotificationConfig()
		.then((config) => ({ config, error: null as string | null }))
		.catch((err) => ({
			config: null,
			error: err instanceof Error ? err.message : "ERR_REQUEST_FAILED",
		}));
	const { config, error: loadError } = configResult;

	const alert =
		status && code ? (
			<p
				className={
					status === "error"
						? "alert alert-enter error"
						: "alert alert-enter success"
				}
				role={status === "error" ? "alert" : "status"}
				aria-live={status === "error" ? "assertive" : "polite"}
			>
				{getFlashMessage(code)}
			</p>
		) : null;

	return (
		<div className="folo-page-shell folo-unified-shell">
			<div className="folo-page-header">
				<p className="folo-page-kicker">{copy.kicker}</p>
				<h1 className="folo-page-title" data-route-heading tabIndex={-1}>
					{copy.heroTitle}
				</h1>
				<p className="folo-page-subtitle">{copy.heroSubtitle}</p>
			</div>

			{alert}
			{loadError ? (
				<Card
					className="folo-surface border-destructive/40 bg-destructive/5"
					role="alert"
					aria-live="assertive"
				>
					<CardHeader className="gap-2">
						<CardTitle className="text-base">{copy.loadErrorTitle}</CardTitle>
						<CardDescription>
							{getFlashMessage(
								loadError.startsWith("ERR_") ? loadError : "ERR_REQUEST_FAILED",
							)}
						</CardDescription>
					</CardHeader>
					<CardContent className="pt-0">
						<Button asChild variant="outline" size="sm">
							<Link href="/settings">{copy.retryCurrentPage}</Link>
						</Button>
					</CardContent>
				</Card>
			) : null}

			<Card className="folo-surface border-border/70">
				<CardHeader className="gap-2">
					<h2 className="text-xl font-semibold">{copy.configSectionTitle}</h2>
					{config ? (
						<CardDescription>
							{copy.configDates
								.replace(
									"{createdAt}",
									formatDateTime(config.created_at) || "-",
								)
								.replace(
									"{updatedAt}",
									formatDateTime(config.updated_at) || "-",
								)}
						</CardDescription>
					) : null}
				</CardHeader>
				<CardContent>
					<form action={updateNotificationConfigAction} className="grid gap-4">
						<WebActionSessionHiddenInput sessionToken={sessionToken} />
						<FormCheckboxField
							name="enabled"
							label={copy.enabledLabel}
							defaultChecked={config?.enabled ?? true}
						/>
						<FormInputField
							id="to_email"
							name="to_email"
							label={copy.toEmailLabel}
							type="email"
							defaultValue={config?.to_email ?? ""}
							placeholder="ops@example.com"
						/>
						<FormCheckboxField
							name="daily_digest_enabled"
							label={copy.dailyDigestLabel}
							defaultChecked={config?.daily_digest_enabled ?? false}
						/>
						<FormInputField
							id="daily_digest_hour_utc"
							name="daily_digest_hour_utc"
							label={copy.dailyDigestHourLabel}
							type="number"
							min={0}
							max={23}
							defaultValue={config?.daily_digest_hour_utc ?? ""}
							data-disabled-unless-checked="daily_digest_enabled"
							data-field-kind="identifier"
							aria-describedby="daily-digest-hour-utc-help"
							disabled={!config?.daily_digest_enabled}
						/>
						<FormFieldHint id="daily-digest-hour-utc-help">
							{copy.dailyDigestHint}
						</FormFieldHint>
						<FormCheckboxField
							name="failure_alert_enabled"
							label={copy.failureAlertLabel}
							defaultChecked={config?.failure_alert_enabled ?? true}
						/>
						<SubmitButton
							pendingLabel={copy.savePending}
							statusText={copy.saveStatus}
						>
							{copy.saveButton}
						</SubmitButton>
					</form>
				</CardContent>
			</Card>

			<Card className="folo-surface border-border/70">
				<CardHeader className="gap-2">
					<h2 className="text-xl font-semibold">{copy.testSectionTitle}</h2>
					<CardDescription>
						{config?.to_email
							? copy.testRecipientDescription.replace(
									"{email}",
									config.to_email,
								)
							: copy.testRecipientMissing}
					</CardDescription>
				</CardHeader>
				<CardContent>
					<form action={sendTestNotificationAction} className="grid gap-4">
						<WebActionSessionHiddenInput sessionToken={sessionToken} />
						<FormInputField
							id="test_to_email"
							name="to_email"
							label={copy.overrideRecipientLabel}
							type="email"
							placeholder={copy.overrideRecipientPlaceholder}
						/>
						<FormInputField
							id="test_subject"
							name="subject"
							label={copy.subjectLabel}
							type="text"
							placeholder={copy.subjectPlaceholder}
						/>
						<FormField>
							<FormFieldLabel htmlFor="test_body">
								{copy.bodyLabel}
							</FormFieldLabel>
							<Textarea
								id="test_body"
								name="body"
								rows={4}
								placeholder={copy.bodyPlaceholder}
							/>
						</FormField>
						<SubmitButton
							pendingLabel={copy.sendPending}
							statusText={copy.sendStatus}
						>
							{copy.sendButton}
						</SubmitButton>
					</form>
				</CardContent>
			</Card>
		</div>
	);
}
