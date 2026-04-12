import type { Metadata } from "next";
import Link from "next/link";

import { getActionSessionTokenForForm } from "@/app/action-security";
import { getFlashMessage } from "@/app/flash-message";
import { upsertSubscriptionAction } from "@/app/subscriptions/actions";
import {
	FormCheckboxField,
	FormInputField,
	FormSelectField,
} from "@/components/form-field";
import { ManualSourceIntakePanel } from "@/components/manual-source-intake-panel";
import { SourceIdentityCard } from "@/components/source-identity-card";
import { SubmitButton } from "@/components/submit-button";
import { SubscriptionBatchPanel } from "@/components/subscription-batch-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
} from "@/components/ui/card";
import { apiClient } from "@/lib/api/client";
import type {
	SubscriptionTemplate,
	SubscriptionTemplateCatalogResponse,
} from "@/lib/api/types";
import { editorialSans, editorialSerif } from "@/lib/editorial-fonts";
import { getLocaleMessages } from "@/lib/i18n/messages";
import {
	resolveSearchParams,
	type SearchParamsInput,
} from "@/lib/search-params";
import { buildProductMetadata } from "@/lib/seo";
import { resolveSubscriptionIdentity } from "@/lib/source-identity";

const subscriptionsCopy = getLocaleMessages().subscriptionsPage;

export const metadata: Metadata = buildProductMetadata({
	title: subscriptionsCopy.metadataTitle,
	description: subscriptionsCopy.metadataDescription,
	route: "subscriptions",
});

type SubscriptionsPageProps = {
	searchParams?: SearchParamsInput;
};

type TemplatePresentation = SubscriptionTemplate;
type SupportTier = SubscriptionTemplateCatalogResponse["support_tiers"][number];

const CATEGORY_KEYS = ["misc", "tech", "creator", "macro", "ops"] as const;

const LEGACY_TEMPLATE_IDS: Record<string, string> = {
	bilibili_creator: "bilibili_user_video",
	rsshub_route: "generic_rsshub_route",
	generic_rss: "generic_rss_feed",
};

function normalizeTemplateCatalog(
	payload: SubscriptionTemplateCatalogResponse,
): TemplatePresentation[] {
	return payload.templates;
}

function renderAlert(status: string, code: string) {
	if (!status || !code) {
		return null;
	}
	const isError = status === "error";
	if (isError) {
		return (
			<p className="alert alert-enter error" role="alert" aria-live="assertive">
				{getFlashMessage(code)}
			</p>
		);
	}
	return (
		<output
			className="alert alert-enter success"
			aria-live="polite"
			aria-atomic="true"
		>
			{getFlashMessage(code)}
		</output>
	);
}

function getTemplateHref(templateId: string): string {
	return `/subscriptions?template=${encodeURIComponent(templateId)}`;
}

function normalizeTemplateId(rawTemplate: string): string | null {
	if (!rawTemplate) {
		return null;
	}
	return LEGACY_TEMPLATE_IDS[rawTemplate] ?? rawTemplate;
}

function findTemplate(
	templates: TemplatePresentation[],
	rawTemplate: string,
): TemplatePresentation | null {
	if (templates.length === 0) {
		return null;
	}
	const normalizedId = normalizeTemplateId(rawTemplate);
	return (
		templates.find((template) => template.id === normalizedId) ?? templates[0]
	);
}

function findSupportTier(
	supportTiers: SupportTier[],
	template: TemplatePresentation | null,
): SupportTier | null {
	if (!template) {
		return null;
	}
	return supportTiers.find((tier) => tier.id === template.support_tier) ?? null;
}

function humanizeToken(value: string): string {
	if (value === "rsshub") {
		return "RSSHub";
	}
	if (value === "generic") {
		return "Generic";
	}
	return value
		.split(/[_-]+/)
		.filter(Boolean)
		.map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
		.join(" ");
}

function supportBadgeClass(level: string): string {
	if (level === "strong_supported") {
		return "border-emerald-500/40 bg-emerald-500/10 text-emerald-700";
	}
	if (level === "generic_supported") {
		return "border-sky-500/40 bg-sky-500/10 text-sky-700";
	}
	return "border-amber-500/40 bg-amber-500/10 text-amber-700";
}

function provingBadgeClass(): string {
	return "border-amber-500/40 bg-amber-500/10 text-amber-700";
}

function uniqueTemplateValues(
	templates: TemplatePresentation[],
	pick: (template: TemplatePresentation) => string,
): string[] {
	return Array.from(
		new Set(
			templates
				.map((template) => pick(template).trim())
				.filter((value) => value.length > 0),
		),
	);
}

function templatesForSupportTier(
	templates: TemplatePresentation[],
	supportTier: string,
): TemplatePresentation[] {
	return templates.filter((template) => template.support_tier === supportTier);
}

export default async function SubscriptionsPage({
	searchParams,
}: SubscriptionsPageProps) {
	const copy = getLocaleMessages().subscriptionsPage;
	const { status, code, template } = await resolveSearchParams(searchParams, [
		"status",
		"code",
		"template",
	] as const);
	const sessionToken = getActionSessionTokenForForm();
	const [subscriptionsResult, templateCatalogResult] = await Promise.all([
		apiClient
			.listSubscriptions()
			.then((data) => ({ data, errorCode: null as string | null }))
			.catch(() => ({
				data: [] as Awaited<ReturnType<typeof apiClient.listSubscriptions>>,
				errorCode: "ERR_REQUEST_FAILED",
			})),
		apiClient
			.listSubscriptionTemplates()
			.then((data) => ({ data, errorCode: null as string | null }))
			.catch(() => ({
				data: {
					support_tiers: [],
					templates: [],
				} satisfies SubscriptionTemplateCatalogResponse,
				errorCode: "ERR_REQUEST_FAILED",
			})),
	]);
	const subscriptions = subscriptionsResult.data;
	const templateCatalog = templateCatalogResult.data;
	const templates = normalizeTemplateCatalog(templateCatalog);
	const platformOptions = uniqueTemplateValues(
		templates,
		(entry) => entry.platform,
	).map((value) => ({
		value,
		label:
			value === "youtube"
				? copy.platformOptions.youtube
				: value === "bilibili"
					? copy.platformOptions.bilibili
					: value === "rss"
						? copy.platformOptions.rss
						: humanizeToken(value),
	}));
	const sourceTypeOptions = uniqueTemplateValues(
		templates,
		(entry) => entry.source_type,
	).map((value) => ({
		value,
		label:
			value === "url"
				? copy.sourceTypeOptions.url
				: value === "youtube_channel_id"
					? copy.sourceTypeOptions.youtubeChannelId
					: value === "bilibili_uid"
						? copy.sourceTypeOptions.bilibiliUid
						: value === "rsshub_route"
							? copy.adapterTypeOptions.rsshubRoute
							: humanizeToken(value),
	}));
	const adapterTypeOptions = uniqueTemplateValues(
		templates,
		(entry) => entry.adapter_type,
	).map((value) => ({
		value,
		label:
			copy.adapterTypeOptions[
				value === "rsshub_route" ? "rsshubRoute" : "rssGeneric"
			],
	}));
	const categoryOptions = CATEGORY_KEYS.map((value) => ({
		value,
		label: copy.categoryOptions[value],
	}));
	const platformLabelMap = new Map<string, string>(
		platformOptions.map((option) => [option.value, option.label]),
	);
	const sourceTypeLabelMap = new Map<string, string>(
		sourceTypeOptions.map((option) => [option.value, option.label]),
	);
	const adapterLabelMap = new Map<string, string>(
		adapterTypeOptions.map((option) => [option.value, option.label]),
	);
	const selectedTemplate = findTemplate(templates, template.trim());
	const selectedSupportTier = findSupportTier(
		templateCatalog.support_tiers,
		selectedTemplate,
	);
	const genericTemplates = templatesForSupportTier(
		templates,
		"generic_supported",
	);
	const provingTemplates = genericTemplates.filter(
		(templateOption) =>
			Boolean(templateOption.proof_boundary) ||
			Boolean(templateOption.evidence_note),
	);
	const pageErrorCode =
		subscriptionsResult.errorCode ?? templateCatalogResult.errorCode;
	const highlightedSubscriptions = subscriptions.slice(0, 6);

	return (
		<div
			className={`folo-page-shell folo-unified-shell ${editorialSans.className}`}
		>
			<div className="folo-page-header">
				<p className="folo-page-kicker">{copy.kicker}</p>
				<h1
					className={`folo-page-title ${editorialSerif.className}`}
					data-route-heading
					tabIndex={-1}
				>
					{copy.heroTitle}
				</h1>
				<p className="folo-page-subtitle">{copy.heroSubtitle}</p>
			</div>

			{renderAlert(status, code)}
			{pageErrorCode ? (
				<Card
					className="folo-surface border-destructive/40 bg-destructive/5"
					role="alert"
					aria-live="assertive"
				>
					<CardHeader className="gap-2">
						<h2 className="text-base font-semibold">{copy.loadErrorTitle}</h2>
						<CardDescription>{getFlashMessage(pageErrorCode)}</CardDescription>
					</CardHeader>
					<CardContent className="pt-0">
						<Button asChild variant="outline" size="sm">
							<Link href="/subscriptions">{copy.retryCurrentPageButton}</Link>
						</Button>
					</CardContent>
				</Card>
			) : null}

			<section className="grid gap-4 xl:grid-cols-[1.28fr_0.92fr]">
				<Card className="folo-surface border-border/70 bg-gradient-to-br from-background via-background to-rose-50/60">
					<CardHeader className="gap-2">
						<h2
							className={`text-2xl font-semibold ${editorialSerif.className}`}
						>
							Tracked universes
						</h2>
						<CardDescription>
							Start by seeing who already belongs to your reading desk. This
							frontstage should feel like an atlas of sources, not a tax form.
						</CardDescription>
					</CardHeader>
					<CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
						{highlightedSubscriptions.length ? (
							highlightedSubscriptions.map((subscription) => (
								<SourceIdentityCard
									key={subscription.id}
									identity={resolveSubscriptionIdentity(subscription)}
									compact
								/>
							))
						) : (
							<div className="rounded-[1.2rem] border border-dashed border-border/60 bg-background/70 p-4 text-sm text-muted-foreground">
								No tracked universes yet. Use the workbench below to create the
								first one and make today&apos;s intake feel attached to a real
								source world.
							</div>
						)}
					</CardContent>
				</Card>

				<Card className="folo-surface border-border/70">
					<CardHeader className="gap-2">
						<h2
							className={`text-2xl font-semibold ${editorialSerif.className}`}
						>
							Intake posture
						</h2>
						<CardDescription>
							Strong lanes should feel immediate. General lanes should stay
							honest about proof boundaries. Manual intake should always tell
							you whether an input belongs to an existing universe or starts a
							new one.
						</CardDescription>
					</CardHeader>
					<CardContent className="space-y-3 text-sm text-muted-foreground">
						<div className="rounded-[1.1rem] border border-border/60 bg-muted/20 p-4">
							<p className="font-medium text-foreground">
								1. Pick the universe
							</p>
							<p className="mt-2">
								Choose a strong-supported lane when you know the creator, or a
								general lane when the source is only proven as feed intake.
							</p>
						</div>
						<div className="rounded-[1.1rem] border border-border/60 bg-muted/20 p-4">
							<p className="font-medium text-foreground">
								2. Run manual intake
							</p>
							<p className="mt-2">
								The result cards below should tell you whether the input matched
								a tracked universe, created a new one, or stayed a one-off lane.
							</p>
						</div>
						<div className="rounded-[1.1rem] border border-border/60 bg-muted/20 p-4">
							<p className="font-medium text-foreground">3. Read the product</p>
							<p className="mt-2">
								Use{" "}
								<Link href="/feed" className="underline underline-offset-4">
									Feed
								</Link>{" "}
								and{" "}
								<Link href="/reader" className="underline underline-offset-4">
									Reader
								</Link>{" "}
								as the frontstage once the source universe has materialized.
							</p>
						</div>
					</CardContent>
				</Card>
			</section>

			<section className="grid gap-4 xl:grid-cols-[1.3fr_0.9fr]">
				<Card className="folo-surface border-border/70">
					<CardHeader className="gap-2">
						<h2 className="text-xl font-semibold">{copy.supportMatrixTitle}</h2>
						<CardDescription>{copy.supportMatrixDescription}</CardDescription>
					</CardHeader>
					<CardContent className="grid gap-3 md:grid-cols-2">
						{templateCatalog.support_tiers.map((tier) => (
							<div
								key={tier.id}
								className="rounded-xl border border-border/60 bg-muted/20 p-4"
							>
								<Badge variant="outline" className={supportBadgeClass(tier.id)}>
									{tier.label}
								</Badge>
								<p className="mt-3 font-medium">{tier.label}</p>
								<p className="mt-2 text-sm text-muted-foreground">
									{tier.description}
								</p>
								<div className="mt-3 flex flex-wrap gap-2">
									{templatesForSupportTier(templates, tier.id).map(
										(templateOption) => (
											<Badge
												key={`${tier.id}-${templateOption.id}`}
												variant="outline"
											>
												{templateOption.label}
											</Badge>
										),
									)}
								</div>
							</div>
						))}
						<div className="rounded-xl border border-border/60 bg-muted/20 p-4">
							<Badge variant="outline" className={provingBadgeClass()}>
								{copy.supportLevels.proving.title}
							</Badge>
							<p className="mt-3 font-medium">
								{copy.supportLevels.proving.title}
							</p>
							<p className="mt-2 text-sm text-muted-foreground">
								{copy.supportLevels.proving.description}
							</p>
							<div className="mt-3 flex flex-wrap gap-2">
								{provingTemplates.map((templateOption) => (
									<Badge key={`proving-${templateOption.id}`} variant="outline">
										{templateOption.label}
									</Badge>
								))}
							</div>
						</div>
					</CardContent>
				</Card>

				<Card className="folo-surface border-border/70">
					<CardHeader className="gap-2">
						<h2 className="text-xl font-semibold">{copy.intakeGuideTitle}</h2>
						<CardDescription>{copy.intakeGuideDescription}</CardDescription>
					</CardHeader>
					<CardContent className="space-y-4">
						{selectedTemplate && selectedSupportTier ? (
							<>
								<div className="space-y-2">
									<div className="flex flex-wrap items-center gap-2">
										<p className="font-medium">{selectedTemplate.label}</p>
										<Badge
											variant="outline"
											className={supportBadgeClass(
												selectedTemplate.support_tier,
											)}
										>
											{selectedSupportTier.label}
										</Badge>
									</div>
									<p className="text-sm text-muted-foreground">
										{selectedTemplate.description}
									</p>
								</div>
								<dl className="grid gap-3 text-sm">
									<div>
										<dt className="font-medium">
											{copy.guideLabels.supportLevel}
										</dt>
										<dd className="flex flex-wrap items-center gap-2 text-muted-foreground">
											<span>{selectedSupportTier.label}</span>
											{selectedTemplate.support_tier === "generic_supported" ? (
												<Badge
													variant="outline"
													className={provingBadgeClass()}
												>
													{copy.supportLevels.proving.title}
												</Badge>
											) : null}
										</dd>
									</div>
									<div>
										<dt className="font-medium">{copy.guideLabels.platform}</dt>
										<dd className="text-muted-foreground">
											{platformLabelMap.get(selectedTemplate.platform) ??
												humanizeToken(selectedTemplate.platform)}
										</dd>
									</div>
									<div>
										<dt className="font-medium">
											{copy.guideLabels.sourceType}
										</dt>
										<dd className="text-muted-foreground">
											{sourceTypeLabelMap.get(selectedTemplate.source_type) ??
												humanizeToken(selectedTemplate.source_type)}
										</dd>
									</div>
									<div>
										<dt className="font-medium">
											{copy.guideLabels.adapterType}
										</dt>
										<dd className="text-muted-foreground">
											{adapterLabelMap.get(selectedTemplate.adapter_type) ??
												selectedTemplate.adapter_type}
										</dd>
									</div>
									<div>
										<dt className="font-medium">{copy.guideLabels.fillNow}</dt>
										<dd className="text-muted-foreground">
											{selectedTemplate.fill_now ||
												selectedTemplate.source_value_placeholder ||
												copy.placeholders.sourceValue}
										</dd>
									</div>
									<div>
										<dt className="font-medium">
											{copy.guideLabels.proofBoundary}
										</dt>
										<dd className="text-muted-foreground">
											{selectedTemplate.proof_boundary ||
												selectedTemplate.evidence_note ||
												selectedSupportTier.description}
										</dd>
									</div>
								</dl>
							</>
						) : (
							<p className="text-sm text-muted-foreground">
								{getFlashMessage("ERR_REQUEST_FAILED")}
							</p>
						)}
						<Button asChild variant="outline" size="sm">
							<Link href="/trends">{copy.openMergedStoriesButton}</Link>
						</Button>
					</CardContent>
				</Card>
			</section>

			<section>
				<ManualSourceIntakePanel
					copy={copy.manualIntake}
					sessionToken={sessionToken}
				/>
			</section>

			<section>
				<Card className="folo-surface border-border/70">
					<CardHeader className="gap-2">
						<h2 className="text-xl font-semibold">
							{copy.templateSectionTitle}
						</h2>
						<CardDescription>{copy.templateSectionDescription}</CardDescription>
					</CardHeader>
					<CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
						{templates.map((templateOption) => {
							const supportTier =
								templateCatalog.support_tiers.find(
									(tier) => tier.id === templateOption.support_tier,
								) ?? null;
							const isSelected = templateOption.id === selectedTemplate?.id;
							return (
								<article
									key={templateOption.id}
									className={`rounded-xl border p-4 ${
										isSelected
											? "border-primary/40 bg-primary/5"
											: "border-border/60 bg-muted/20"
									}`}
								>
									<div className="flex items-start justify-between gap-3">
										<h3 className="text-base font-semibold">
											{templateOption.label}
										</h3>
										<div className="flex flex-wrap justify-end gap-2">
											<Badge
												variant="outline"
												className={supportBadgeClass(
													templateOption.support_tier,
												)}
											>
												{supportTier?.label ?? templateOption.support_tier}
											</Badge>
											{templateOption.support_tier === "generic_supported" ? (
												<Badge
													variant="outline"
													className={provingBadgeClass()}
												>
													{copy.supportLevels.proving.title}
												</Badge>
											) : null}
										</div>
									</div>
									<p className="mt-3 text-sm text-muted-foreground">
										{templateOption.description}
									</p>
									<p className="mt-3 text-sm text-muted-foreground">
										{templateOption.fill_now ||
											templateOption.source_value_placeholder ||
											copy.placeholders.sourceValue}
									</p>
									<p className="mt-3 text-sm text-muted-foreground">
										{templateOption.proof_boundary ||
											templateOption.evidence_note ||
											supportTier?.description ||
											copy.supportMatrixDescription}
									</p>
									<div className="mt-4">
										<Button
											asChild
											variant={isSelected ? "hero" : "outline"}
											size="sm"
										>
											<Link href={getTemplateHref(templateOption.id)}>
												{isSelected
													? copy.templateSelectedButton
													: copy.templateButton}
											</Link>
										</Button>
									</div>
								</article>
							);
						})}
					</CardContent>
				</Card>
			</section>

			<section className="grid gap-4 xl:grid-cols-[1.35fr_0.95fr]">
				<Card className="folo-surface border-border/70">
					<CardHeader className="gap-2">
						<h2 className="text-xl font-semibold">{copy.editorTitle}</h2>
						<CardDescription>{copy.editorDescription}</CardDescription>
					</CardHeader>
					<CardContent>
						{selectedTemplate ? (
							<form
								action={upsertSubscriptionAction}
								className="grid gap-5 md:grid-cols-2"
								data-auto-disable-required="true"
							>
								<input
									type="hidden"
									name="session_token"
									value={sessionToken}
									suppressHydrationWarning
								/>
								<FormSelectField
									id="platform"
									name="platform"
									label={copy.formLabels.platform}
									defaultValue={selectedTemplate.platform}
									options={platformOptions}
								/>
								<FormSelectField
									id="source_type"
									name="source_type"
									label={copy.formLabels.sourceType}
									defaultValue={selectedTemplate.source_type}
									options={sourceTypeOptions}
								/>
								<FormInputField
									id="source_value"
									name="source_value"
									label={copy.formLabels.sourceValue}
									required
									placeholder={
										selectedTemplate.source_value_placeholder ??
										copy.placeholders.sourceValue
									}
								/>
								<FormSelectField
									id="adapter_type"
									name="adapter_type"
									label={copy.formLabels.adapterType}
									defaultValue={selectedTemplate.adapter_type}
									options={adapterTypeOptions}
								/>
								<FormInputField
									id="source_url"
									name="source_url"
									label={copy.formLabels.sourceUrl}
									type="url"
									required={selectedTemplate.source_url_required}
									placeholder={
										selectedTemplate.source_url_placeholder ??
										copy.placeholders.sourceUrl
									}
								/>
								<FormInputField
									id="rsshub_route"
									name="rsshub_route"
									label={copy.formLabels.rsshubRoute}
									placeholder={
										selectedTemplate.rsshub_route_hint ??
										copy.placeholders.rsshubRoute
									}
								/>
								<FormSelectField
									id="category"
									name="category"
									label={copy.formLabels.category}
									defaultValue={selectedTemplate.category ?? "misc"}
									options={categoryOptions}
								/>
								<FormInputField
									id="tags"
									name="tags"
									label={copy.formLabels.tags}
									placeholder={copy.placeholders.tags}
								/>
								<FormInputField
									id="priority"
									name="priority"
									label={copy.formLabels.priority}
									type="number"
									min={0}
									max={100}
									defaultValue={50}
								/>
								<FormCheckboxField
									name="enabled"
									label={copy.formLabels.enabled}
									defaultChecked
									fieldClassName="md:col-span-2"
								/>
								<div className="md:col-span-2">
									<SubmitButton
										pendingLabel={copy.savePending}
										statusText={copy.saveStatus}
									>
										{copy.saveButton}
									</SubmitButton>
								</div>
							</form>
						) : (
							<p className="text-sm text-muted-foreground">
								{getFlashMessage("ERR_REQUEST_FAILED")}
							</p>
						)}
					</CardContent>
				</Card>

				<Card className="folo-surface border-border/70">
					<CardHeader className="gap-2">
						<h2 className="text-xl font-semibold">
							{selectedSupportTier?.label ?? copy.loadErrorTitle}
						</h2>
						<CardDescription>
							{selectedSupportTier?.description ??
								getFlashMessage("ERR_REQUEST_FAILED")}
						</CardDescription>
					</CardHeader>
					<CardContent className="space-y-4 text-sm text-muted-foreground">
						<p>
							{selectedTemplate?.fill_now ??
								selectedTemplate?.source_value_placeholder ??
								getFlashMessage("ERR_REQUEST_FAILED")}
						</p>
						<p>
							{selectedTemplate?.proof_boundary ??
								selectedTemplate?.evidence_note ??
								selectedSupportTier?.description ??
								getFlashMessage("ERR_REQUEST_FAILED")}
						</p>
					</CardContent>
				</Card>
			</section>

			<section>
				<Card className="folo-surface border-border/70">
					<CardHeader className="gap-2">
						<h2 className="text-xl font-semibold">{copy.currentTitle}</h2>
						<CardDescription>
							<output
								className="text-sm text-muted-foreground"
								aria-live="polite"
								aria-atomic="true"
							>
								{copy.loadedPrefix} {subscriptions.length} {copy.loadedSuffix}
							</output>
							<p className="text-sm text-muted-foreground">
								{copy.currentDescription}
							</p>
						</CardDescription>
					</CardHeader>
					<CardContent>
						<SubscriptionBatchPanel
							subscriptions={subscriptions}
							sessionToken={sessionToken}
						/>
					</CardContent>
				</Card>
			</section>
		</div>
	);
}
