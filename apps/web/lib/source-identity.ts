import type {
	DigestFeedItem,
	ManualSourceIntakeResult,
	SourceIdentityRef,
	Subscription,
} from "@sourceharbor/sdk";

export type SourceRelationKind =
	| "matched_subscription"
	| "new_source_universe"
	| "manual_one_off"
	| "subscription_tracked"
	| "manual_injected"
	| "unmatched_source"
	| "subscription_candidate"
	| string;

export type SourceIdentityModel = {
	title: string;
	subtitle: string;
	description?: string;
	eyebrow?: string;
	thumbnailUrl: string | null;
	avatarUrl: string | null;
	avatarLabel: string;
	relationKind: SourceRelationKind;
	relationLabel: string;
	meta: string[];
};

const PLATFORM_META: Record<
	string,
	{ label: string; accent: string; wash: string }
> = {
	youtube: { label: "YouTube", accent: "#ff0033", wash: "#fff1f2" },
	bilibili: { label: "Bilibili", accent: "#0ea5e9", wash: "#e0f2fe" },
	rsshub: { label: "RSSHub", accent: "#7c3aed", wash: "#f5f3ff" },
	rss: { label: "RSS", accent: "#0f766e", wash: "#ecfeff" },
	generic: { label: "Generic", accent: "#18181b", wash: "#f4f4f5" },
};

function normalizePlatform(platform: string | null | undefined): string {
	const normalized = String(platform || "")
		.trim()
		.toLowerCase();
	if (normalized === "rss_generic") return "rss";
	return normalized || "generic";
}

function platformMeta(platform: string | null | undefined) {
	return PLATFORM_META[normalizePlatform(platform)] ?? PLATFORM_META.generic;
}

function initials(label: string | null | undefined): string {
	const value = String(label || "").trim();
	if (!value) return "SH";
	const segments = value.replace(/[_-]+/g, " ").split(/\s+/).filter(Boolean);
	if (segments.length >= 2) {
		return `${segments[0][0]}${segments[1][0]}`.toUpperCase();
	}
	const compact = value.replace(/[^a-zA-Z0-9]/g, "");
	return (compact.slice(0, 2) || "SH").toUpperCase();
}

function svgDataUrl({
	primary,
	secondary,
	platform,
	square,
}: {
	primary: string;
	secondary: string;
	platform: string | null | undefined;
	square: boolean;
}): string {
	const meta = platformMeta(platform);
	const radius = square ? 28 : 52;
	const svg = `
<svg xmlns="http://www.w3.org/2000/svg" width="640" height="400" viewBox="0 0 640 400" role="img" aria-label="${primary}">
  <rect width="640" height="400" rx="${radius}" fill="${meta.wash}" />
  <rect x="22" y="22" width="596" height="356" rx="${radius}" fill="rgba(255,255,255,0.62)" />
  <text x="40" y="164" font-family="ui-sans-serif, system-ui, sans-serif" font-size="92" font-weight="700" fill="${meta.accent}">${secondary}</text>
  <text x="40" y="248" font-family="ui-sans-serif, system-ui, sans-serif" font-size="34" fill="#18181B">${primary.slice(0, 44)}</text>
  <text x="40" y="306" font-family="ui-monospace, monospace" font-size="24" fill="#52525B">${meta.label}</text>
</svg>`.trim();
	return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

function extractYouTubeVideoId(
	rawUrl: string | null | undefined,
): string | null {
	try {
		const parsed = new URL(String(rawUrl || ""));
		if (parsed.hostname === "youtu.be") {
			return parsed.pathname.replace(/^\//, "") || null;
		}
		const queryId = parsed.searchParams.get("v");
		if (queryId) return queryId;
		const segments = parsed.pathname.split("/").filter(Boolean);
		if (segments.length >= 2 && ["shorts", "live"].includes(segments[0])) {
			return segments[1] || null;
		}
		return null;
	} catch {
		return null;
	}
}

export function buildThumbnailUrl({
	platform,
	url,
	title,
}: {
	platform: string | null | undefined;
	url: string | null | undefined;
	title: string;
}): string | null {
	const normalizedPlatform = normalizePlatform(platform);
	const youtubeVideoId = extractYouTubeVideoId(url);
	if (youtubeVideoId) {
		return `https://i.ytimg.com/vi/${youtubeVideoId}/hqdefault.jpg`;
	}
	return svgDataUrl({
		primary: title,
		secondary: platformMeta(platform).label.slice(0, 6).toUpperCase(),
		platform: normalizedPlatform,
		square: true,
	});
}

function fallbackAvatarUrl(label: string, platform: string | null | undefined) {
	return svgDataUrl({
		primary: label,
		secondary: initials(label),
		platform,
		square: false,
	});
}

function relationLabel(kind: SourceRelationKind): string {
	if (kind === "matched_subscription") return "Tracked universe";
	if (kind === "new_source_universe") return "New universe";
	if (kind === "manual_one_off") return "Reading today";
	if (kind === "subscription_tracked") return "Tracked source";
	if (kind === "manual_injected") return "Reading today";
	if (kind === "subscription_candidate") return "Needs review";
	return "Unmatched source";
}

function supportTierLabel(value: string | null | undefined): string | null {
	const normalized = String(value || "")
		.trim()
		.toLowerCase();
	if (!normalized) return null;
	if (normalized === "strong_supported") return "Strong path";
	if (normalized === "generic_supported") return "General path";
	if (normalized === "needs_proof") return "Needs proof";
	return normalized
		.split(/[_-]+/)
		.filter(Boolean)
		.map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
		.join(" ");
}

function matchDetailLabel(value: string | null | undefined): string | null {
	const normalized = String(value || "").trim();
	if (!normalized) return null;
	return `Matched by ${normalized.replace(/[_-]+/g, " ")}`;
}

function confidenceLabel(value: string | null | undefined): string | null {
	const normalized = String(value || "").trim();
	if (!normalized) return null;
	return `${normalized.charAt(0).toUpperCase()}${normalized.slice(1)} confidence`;
}

function safeList(items: Array<string | null | undefined>) {
	return items.map((item) => String(item || "").trim()).filter(Boolean);
}

export function resolveSubscriptionIdentity(
	subscription: Subscription,
): SourceIdentityModel {
	const title =
		subscription.creator_display_name?.trim() ||
		subscription.source_name?.trim() ||
		subscription.source_value.trim();
	const platform = normalizePlatform(subscription.platform);
	return {
		title,
		subtitle:
			subscription.source_universe_label?.trim() ||
			platformMeta(platform).label,
		description:
			subscription.source_homepage_url?.trim() ||
			subscription.source_url?.trim() ||
			subscription.rsshub_route,
		eyebrow:
			subscription.support_tier === "strong_supported"
				? "Strong path"
				: "General path",
		thumbnailUrl:
			subscription.thumbnail_url ||
			buildThumbnailUrl({
				platform,
				url: subscription.source_homepage_url || subscription.source_url,
				title,
			}),
		avatarUrl: subscription.avatar_url || fallbackAvatarUrl(title, platform),
		avatarLabel: subscription.avatar_label || initials(title),
		relationKind: "matched_subscription",
		relationLabel:
			subscription.identity_status === "derived_identity"
				? "Tracked universe"
				: "Canonical universe",
		meta: safeList([
			platformMeta(platform).label,
			subscription.content_profile,
			subscription.category,
			supportTierLabel(subscription.support_tier),
			subscription.priority ? `Priority ${subscription.priority}` : null,
		]),
	};
}

export function resolveManualIntakeIdentity(
	result: ManualSourceIntakeResult,
): SourceIdentityModel {
	const platform = normalizePlatform(result.platform);
	const title =
		result.creator_display_name?.trim() ||
		result.matched_subscription_name?.trim() ||
		result.display_name?.trim() ||
		result.source_value?.trim() ||
		result.source_url?.trim() ||
		"Manual input";
	const relationKind = String(result.relation_kind || "unmatched_source");
	return {
		title,
		subtitle:
			result.source_universe_label?.trim() ||
			result.matched_subscription_name?.trim() ||
			platformMeta(platform).label,
		description: result.message,
		eyebrow:
			result.applied_action === "save_subscription"
				? "Saved to your desk"
				: result.applied_action === "add_to_today"
					? "Reading today"
					: "Needs review",
		thumbnailUrl:
			result.thumbnail_url ||
			buildThumbnailUrl({
				platform,
				url: result.source_url,
				title,
			}),
		avatarUrl: result.avatar_url || fallbackAvatarUrl(title, platform),
		avatarLabel: result.avatar_label || initials(title),
		relationKind,
		relationLabel: relationLabel(relationKind),
		meta: safeList([
			platformMeta(platform).label,
			result.content_profile,
			result.source_universe_label,
			supportTierLabel(result.support_tier),
			matchDetailLabel(result.matched_by),
			confidenceLabel(result.match_confidence),
		]),
	};
}

export function resolveFeedIdentity(item: DigestFeedItem): SourceIdentityModel {
	const platform = normalizePlatform(item.source);
	const title =
		item.canonical_author_name?.trim() ||
		item.canonical_source_name?.trim() ||
		item.source_name.trim() ||
		item.title.trim();
	const relationKind = String(
		item.relation_kind ||
			(item.subscription_id ? "matched_subscription" : "unmatched_source"),
	);
	return {
		title,
		subtitle: item.affiliation_label?.trim() || platformMeta(platform).label,
		description: item.title,
		eyebrow: item.content_type === "video" ? "Preview lane" : "Article preview",
		thumbnailUrl:
			item.thumbnail_url ||
			buildThumbnailUrl({
				platform,
				url: item.video_url,
				title,
			}),
		avatarUrl: item.avatar_url || fallbackAvatarUrl(title, platform),
		avatarLabel: item.avatar_label || initials(title),
		relationKind,
		relationLabel: relationLabel(relationKind),
		meta: safeList([
			platformMeta(platform).label,
			item.affiliation_label,
			item.category,
			item.identity_status === "derived_identity" ? "Linked identity" : null,
			item.saved ? "Saved" : null,
			item.feedback_label || null,
		]),
	};
}

export function resolveReaderSourceIdentity(
	source: SourceIdentityRef,
): SourceIdentityModel {
	const platform = normalizePlatform(source.platform);
	const title =
		source.canonical_author_name?.trim() ||
		source.creator_display_name?.trim() ||
		source.matched_subscription_name?.trim() ||
		source.title.trim();
	const relationKind = String(
		source.relation_kind ||
			(source.source_origin === "subscription_tracked"
				? "subscription_tracked"
				: source.source_origin === "manual_injected"
					? "manual_injected"
					: "unmatched_source"),
	);
	return {
		title,
		subtitle:
			source.affiliation_label?.trim() ||
			source.matched_subscription_name?.trim() ||
			platformMeta(platform).label,
		description: source.digest_preview,
		eyebrow:
			source.source_origin === "manual_injected"
				? "Today's source"
				: "Tracked evidence",
		thumbnailUrl:
			source.thumbnail_url ||
			buildThumbnailUrl({
				platform,
				url: source.source_url,
				title,
			}),
		avatarUrl: source.avatar_url || fallbackAvatarUrl(title, platform),
		avatarLabel: source.avatar_label || initials(title),
		relationKind,
		relationLabel: relationLabel(relationKind),
		meta: safeList([
			platformMeta(platform).label,
			source.affiliation_label,
			source.source_origin === "manual_injected"
				? "Reading today"
				: "Tracked source",
			source.raw_stage_contract?.analysis_mode
				? `Mode ${source.raw_stage_contract.analysis_mode}`
				: null,
			source.raw_stage_contract?.video_contract_satisfied === true
				? "Video-first verified"
				: source.raw_stage_contract?.video_contract_satisfied === false
					? "Video contract gap"
					: null,
			source.identity_status === "derived_identity" ? "Linked identity" : null,
			source.claim_kinds?.length
				? `${source.claim_kinds.length} claim kinds`
				: null,
		]),
	};
}
