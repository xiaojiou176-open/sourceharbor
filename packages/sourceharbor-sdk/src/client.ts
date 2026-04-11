import type {
	ArtifactMarkdownWithMeta,
	AskAnswerResponse,
	ClusterVerdictManifest,
	DigestFeedResponse,
	FeedFeedback,
	FeedFeedbackUpdateRequest,
	IngestPollRequest,
	IngestPollResponse,
	IngestRun,
	IngestRunSummary,
	Job,
	JobCompare,
	JobEvidenceBundle,
	JobStatus,
	KnowledgeCard,
	ManualSourceIntakeRequest,
	ManualSourceIntakeResponse,
	NotificationConfig,
	NotificationConfigUpdateRequest,
	NotificationSendResponse,
	NotificationTestRequest,
	OpsInboxResponse,
	Platform,
	NavigationBrief,
	ReaderBatchMaterialization,
	ReaderDocument,
	ReaderDocumentRepairRequest,
	RetrievalSearchMode,
	RetrievalSearchResponse,
	Subscription,
	SubscriptionCategory,
	SubscriptionTemplateCatalogResponse,
	SubscriptionUpsertRequest,
	SubscriptionUpsertResponse,
	Video,
	VideoProcessRequest,
	VideoProcessResponse,
	Watchlist,
	WatchlistBriefing,
	WatchlistBriefingPage,
	WatchlistTrendResponse,
	WatchlistUpsertRequest,
} from "./types.js";
import {
	buildApiUrl,
	buildApiUrlFromBaseUrl,
	buildArtifactAssetUrlFromBaseUrl,
	sanitizeExternalUrl,
} from "./url.js";

type RequestOptions = Omit<RequestInit, "body"> & {
	body?: unknown;
	webSessionToken?: string | null;
	writeAccessToken?: string | null;
};

export type SourceHarborClientOptions = {
	baseUrl: string;
	fetchImpl?: typeof fetch;
	webSessionToken?: string | null;
	writeAccessToken?: string | null;
};

function asObject(value: unknown): Record<string, unknown> | null {
	if (!value || typeof value !== "object" || Array.isArray(value)) {
		return null;
	}
	return value as Record<string, unknown>;
}

function asString(value: unknown): string {
	return typeof value === "string" ? value : "";
}

function asNullableString(value: unknown): string | null {
	return typeof value === "string" && value.trim() ? value : null;
}

function asBoolean(value: unknown): boolean {
	if (typeof value === "boolean") {
		return value;
	}
	if (typeof value === "string") {
		const normalized = value.trim().toLowerCase();
		if (
			normalized === "true" ||
			normalized === "1" ||
			normalized === "yes" ||
			normalized === "on"
		) {
			return true;
		}
		if (
			normalized === "false" ||
			normalized === "0" ||
			normalized === "no" ||
			normalized === "off" ||
			normalized === ""
		) {
			return false;
		}
		return false;
	}
	if (typeof value === "number") {
		return value !== 0;
	}
	return false;
}

function assertSafeIdentifier(raw: string): string {
	const value = raw.trim();
	if (!/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(value)) {
		throw new Error("ERR_INVALID_IDENTIFIER");
	}
	return value;
}

function normalizeStringMap(value: unknown): Record<string, string> {
	if (!value || typeof value !== "object") {
		return {};
	}

	const entries = Object.entries(value as Record<string, unknown>);
	const normalized: Record<string, string> = {};
	for (const [key, item] of entries) {
		if (typeof item === "string") {
			normalized[key] = item;
		}
	}
	return normalized;
}

function normalizeJob(job: Job): Job {
	return {
		...job,
		step_summary: Array.isArray(job.step_summary) ? job.step_summary : [],
		steps: Array.isArray(job.steps)
			? job.steps
					.map((step) => {
						const record = asObject(step);
						if (!record) {
							return null;
						}
						return {
							...(record as Job["steps"][number]),
							thought_metadata:
								record.thought_metadata &&
								typeof record.thought_metadata === "object" &&
								!Array.isArray(record.thought_metadata)
									? (record.thought_metadata as Record<string, unknown>)
									: {},
						};
					})
					.filter((step): step is Job["steps"][number] => step !== null)
			: [],
		degradations: Array.isArray(job.degradations) ? job.degradations : [],
		artifacts_index: normalizeStringMap(job.artifacts_index),
		mode: job.mode ?? null,
		notification_retry: job.notification_retry ?? null,
	};
}

function normalizeArtifactMarkdownWithMeta(
	payload: unknown,
): ArtifactMarkdownWithMeta {
	const parsed = asObject(payload);
	return {
		markdown: asString(parsed?.markdown),
		meta: asObject(parsed?.meta),
	};
}

function normalizeDigestFeedResponse(payload: unknown): DigestFeedResponse {
	const parsed = asObject(payload);
	const rawItems = Array.isArray(parsed?.items) ? parsed.items : [];
	const items = rawItems
		.map((item): DigestFeedResponse["items"][number] | null => {
			const record = asObject(item);
			if (!record) {
				return null;
			}

			const feedId = asString(record.feed_id).trim();
			const jobId = asString(record.job_id).trim();
			if (!feedId || !jobId) {
				return null;
			}

			const category = asString(record.category).trim();
			const artifactTypeRaw = asString(record.artifact_type).trim();
			const sourceRaw = asString(record.source).trim().toLowerCase();
			const contentTypeRaw = asString(record.content_type).trim().toLowerCase();
			const contentType: "video" | "article" =
				contentTypeRaw === "video" || contentTypeRaw === "article"
					? contentTypeRaw
					: sourceRaw === "youtube" || sourceRaw === "bilibili"
						? "video"
						: "article";
			const cat = category || "misc";
			const safeCategory: DigestFeedResponse["items"][number]["category"] =
				cat === "tech" || cat === "creator" || cat === "macro" || cat === "ops"
					? cat
					: "misc";
			return {
				feed_id: feedId,
				job_id: jobId,
				video_url: asString(record.video_url),
				title: asString(record.title),
				source: asString(record.source),
				source_name: asString(record.source_name),
				canonical_source_name: asNullableString(record.canonical_source_name),
				canonical_author_name: asNullableString(record.canonical_author_name),
				subscription_id: asNullableString(record.subscription_id),
				affiliation_label: asNullableString(record.affiliation_label),
				relation_kind: asNullableString(record.relation_kind),
				thumbnail_url: asNullableString(record.thumbnail_url),
				avatar_url: asNullableString(record.avatar_url),
				avatar_label: asNullableString(record.avatar_label),
				identity_status: asNullableString(record.identity_status),
				category: safeCategory,
				published_at: asString(record.published_at),
				summary_md: asString(record.summary_md),
				artifact_type: artifactTypeRaw === "outline" ? "outline" : "digest",
				content_type: contentType,
				saved: asBoolean(record.saved),
				feedback_label: (() => {
					const raw = asString(record.feedback_label).trim().toLowerCase();
					return raw === "useful" ||
						raw === "noisy" ||
						raw === "dismissed" ||
						raw === "archived"
						? raw
						: null;
				})(),
			};
		})
		.filter(
			(item): item is DigestFeedResponse["items"][number] => item !== null,
		);

	const nextCursorRaw = parsed?.next_cursor;
	return {
		items,
		has_more: asBoolean(parsed?.has_more),
		next_cursor: typeof nextCursorRaw === "string" ? nextCursorRaw : null,
	};
}

function normalizeKnowledgeCards(payload: unknown): KnowledgeCard[] {
	const rawItems = Array.isArray(payload) ? payload : [];
	return rawItems
		.map((item, index): KnowledgeCard | null => {
			const record = asObject(item);
			if (!record) {
				return null;
			}

			const cardType = asString(record.card_type).trim();
			const body = asString(record.body).trim();
			const sourceSection = asString(record.source_section).trim();
			if (!cardType || !body || !sourceSection) {
				return null;
			}

			const rawOrderIndex =
				typeof record.order_index === "number"
					? record.order_index
					: typeof record.ordinal === "number"
						? record.ordinal
						: index;

			return {
				id: asString(record.id) || undefined,
				job_id: asString(record.job_id) || undefined,
				video_id: asString(record.video_id) || undefined,
				card_type: cardType,
				title: asString(record.title) || null,
				body,
				source_section: sourceSection,
				order_index: Number.isFinite(rawOrderIndex) ? rawOrderIndex : index,
				metadata_json: asObject(record.metadata_json) ?? undefined,
				created_at: asString(record.created_at) || undefined,
				updated_at: asString(record.updated_at) || undefined,
			};
		})
		.filter((item): item is KnowledgeCard => item !== null);
}

function normalizeRetrievalSearchResponse(
	payload: unknown,
): RetrievalSearchResponse {
	const parsed = asObject(payload);
	const rawItems = Array.isArray(parsed?.items) ? parsed.items : [];
	return {
		query: asString(parsed?.query),
		top_k:
			typeof parsed?.top_k === "number" && Number.isFinite(parsed.top_k)
				? parsed.top_k
				: 0,
		filters: Object.fromEntries(
			Object.entries(asObject(parsed?.filters) ?? {})
				.filter(([, value]) => typeof value === "string" && value.trim())
				.map(([key, value]) => [key, String(value)]),
		),
		items: rawItems
			.map((item): RetrievalSearchResponse["items"][number] | null => {
				const record = asObject(item);
				if (!record) {
					return null;
				}
				const jobId = asString(record.job_id).trim();
				const videoId = asString(record.video_id).trim();
				const source = asString(record.source).trim().toLowerCase();
				const snippet = asString(record.snippet).trim();
				if (!jobId || !videoId || !source || !snippet) {
					return null;
				}
				if (
					source !== "digest" &&
					source !== "transcript" &&
					source !== "outline" &&
					source !== "knowledge_cards" &&
					source !== "comments" &&
					source !== "meta"
				) {
					return null;
				}
				const normalizedSource =
					source as RetrievalSearchResponse["items"][number]["source"];
				return {
					job_id: jobId,
					video_id: videoId,
					platform: asString(record.platform),
					video_uid: asString(record.video_uid),
					source_url: asString(record.source_url),
					title: asString(record.title) || null,
					kind: asString(record.kind),
					mode: asString(record.mode) || null,
					source: normalizedSource,
					snippet,
					score:
						typeof record.score === "number" && Number.isFinite(record.score)
							? record.score
							: 0,
				};
			})
			.filter(
				(item): item is RetrievalSearchResponse["items"][number] =>
					item !== null,
			),
	};
}

function normalizeRetrievalMode(
	value: RetrievalSearchMode | string | undefined,
): RetrievalSearchMode {
	return value === "semantic" || value === "hybrid" ? value : "keyword";
}

function normalizeTopK(value: number | undefined, fallback: number): number {
	return Number.isFinite(value) && typeof value === "number" && value > 0
		? Math.min(value, 20)
		: fallback;
}

function assertSafeExternalUrl(raw: string): string {
	const normalized = sanitizeExternalUrl(raw);
	if (!normalized) {
		throw new Error("ERR_INVALID_INPUT");
	}
	return normalized;
}

function normalizeErrorCodeCandidate(value: unknown): string | null {
	if (typeof value !== "string") {
		return null;
	}
	const matched = value
		.trim()
		.toUpperCase()
		.match(/\bERR_[A-Z0-9_]+\b/);
	return matched?.[0] ?? null;
}

function parseErrorCodeFromBody(body: string): string | null {
	const fromText = normalizeErrorCodeCandidate(body);
	if (fromText) {
		return fromText;
	}

	let parsed: unknown;
	try {
		parsed = JSON.parse(body);
	} catch {
		return null;
	}
	const asRecord = asObject(parsed);
	if (!asRecord) {
		return null;
	}
	return (
		normalizeErrorCodeCandidate(asRecord.error_code) ??
		normalizeErrorCodeCandidate(asRecord.code) ??
		normalizeErrorCodeCandidate(asRecord.detail) ??
		normalizeErrorCodeCandidate(asRecord.message)
	);
}

async function parseError(response: Response): Promise<string> {
	const body = await response.text().catch(() => "");
	const errorCode = parseErrorCodeFromBody(body);
	if (errorCode) {
		return errorCode;
	}
	if (response.status === 400 || response.status === 422) {
		return "ERR_INVALID_INPUT";
	}
	if (response.status === 404) {
		return "ERR_REQUEST_FAILED";
	}
	if (response.status >= 500) {
		return "ERR_REQUEST_FAILED";
	}
	if (response.status === 401 || response.status === 403) {
		return "ERR_AUTH_REQUIRED";
	}
	return "ERR_REQUEST_FAILED";
}

function isWriteMethod(method: string | undefined): boolean {
	const normalized = method?.trim().toUpperCase() ?? "GET";
	return normalized !== "GET" && normalized !== "HEAD";
}

function buildWriteAuthHeaders(options: RequestOptions): Headers | undefined {
	if (!isWriteMethod(options.method)) {
		return undefined;
	}

	const headers = new Headers(options.headers ?? {});
	const writeAccessToken = options.writeAccessToken?.trim();
	const webSessionToken = options.webSessionToken?.trim();
	if (writeAccessToken) {
		headers.set("X-API-Key", writeAccessToken);
		headers.set("Authorization", `Bearer ${writeAccessToken}`);
		return headers;
	}
	if (webSessionToken) {
		headers.set("X-Web-Session", webSessionToken);
		return headers;
	}

	return headers;
}

async function requestJson<T>(
	path: string,
	options: RequestOptions = {},
	query?: Record<string, string | number | boolean | null | undefined>,
	normalize?: (payload: unknown) => T,
): Promise<T> {
	const url = buildApiUrl(path, query);
	let response: Response;
	try {
		const authHeaders = buildWriteAuthHeaders(options);
		response = await fetch(url, {
			...options,
			cache: "no-store",
			headers: (() => {
				const headers = authHeaders ?? new Headers(options.headers ?? {});
				headers.set("Content-Type", "application/json");
				return headers;
			})(),
			body:
				options.body === undefined ? undefined : JSON.stringify(options.body),
		});
	} catch {
		throw new Error("ERR_REQUEST_FAILED");
	}

	if (!response.ok) {
		const reason = await parseError(response);
		throw new Error(reason);
	}

	if (response.status === 204) {
		return undefined as T;
	}

	const textBody = await response.text().catch(() => "");
	if (!textBody.trim()) {
		throw new Error("ERR_PROTOCOL_EMPTY_BODY");
	}

	let parsed: unknown;
	try {
		parsed = JSON.parse(textBody);
	} catch {
		throw new Error("ERR_REQUEST_FAILED");
	}

	if (normalize) {
		return normalize(parsed);
	}

	return parsed as T;
}

async function requestText(
	path: string,
	query?: Record<string, string | number | boolean | null | undefined>,
): Promise<string> {
	const url = buildApiUrl(path, query);
	let response: Response;
	try {
		response = await fetch(url, { cache: "no-store" });
	} catch {
		throw new Error("ERR_REQUEST_FAILED");
	}
	if (!response.ok) {
		const reason = await parseError(response);
		throw new Error(reason);
	}
	return response.text();
}

function getArtifactMarkdown(params: {
	job_id?: string;
	video_url?: string;
	include_meta: true;
}): Promise<ArtifactMarkdownWithMeta>;
function getArtifactMarkdown(params: {
	job_id?: string;
	video_url?: string;
	include_meta?: false;
}): Promise<string>;
function getArtifactMarkdown(params: {
	job_id?: string;
	video_url?: string;
	include_meta?: boolean;
}): Promise<ArtifactMarkdownWithMeta | string> {
	const safeVideoUrl = params.video_url
		? assertSafeExternalUrl(params.video_url)
		: undefined;
	const safeParams = safeVideoUrl
		? { ...params, video_url: safeVideoUrl }
		: params;
	if (params.include_meta) {
		return requestJson<ArtifactMarkdownWithMeta>(
			"/api/v1/artifacts/markdown",
			{},
			safeParams,
			normalizeArtifactMarkdownWithMeta,
		);
	}

	return requestText("/api/v1/artifacts/markdown", safeParams);
}

export const apiClient = {
	listSubscriptions(params?: {
		platform?: Platform;
		category?: SubscriptionCategory;
		enabled_only?: boolean;
	}) {
		return requestJson<Subscription[]>("/api/v1/subscriptions", {}, params);
	},

	listSubscriptionTemplates() {
		return requestJson<SubscriptionTemplateCatalogResponse>(
			"/api/v1/subscriptions/templates",
		);
	},

		upsertSubscription(
			payload: SubscriptionUpsertRequest,
			options?: { writeAccessToken?: string | null },
		) {
		return requestJson<SubscriptionUpsertResponse>("/api/v1/subscriptions", {
			method: "POST",
			body: payload,
			writeAccessToken: options?.writeAccessToken,
			});
		},

		submitManualSourceIntake(
			payload: ManualSourceIntakeRequest,
			options?: {
				webSessionToken?: string | null;
				writeAccessToken?: string | null;
			},
		) {
			return requestJson<ManualSourceIntakeResponse>(
				"/api/v1/subscriptions/manual-intake",
				{
					method: "POST",
					body: payload,
					webSessionToken: options?.webSessionToken,
					writeAccessToken: options?.writeAccessToken,
				},
			);
		},

		batchUpdateSubscriptionCategory(
			payload: { ids: string[]; category: string },
			options?: {
			webSessionToken?: string | null;
			writeAccessToken?: string | null;
		},
	) {
		return requestJson<{ updated: number }>(
			"/api/v1/subscriptions/batch-update-category",
			{
				method: "POST",
				body: payload,
				webSessionToken: options?.webSessionToken,
				writeAccessToken: options?.writeAccessToken,
			},
		);
	},

	deleteSubscription(
		id: string,
		options?: {
			webSessionToken?: string | null;
			writeAccessToken?: string | null;
		},
	) {
		const safeId = encodeURIComponent(assertSafeIdentifier(id));
		return requestJson<void>(`/api/v1/subscriptions/${safeId}`, {
			method: "DELETE",
			webSessionToken: options?.webSessionToken,
			writeAccessToken: options?.writeAccessToken,
		});
	},

	pollIngest(
		payload: IngestPollRequest,
		options?: {
			webSessionToken?: string | null;
			writeAccessToken?: string | null;
		},
	) {
		return requestJson<IngestPollResponse>("/api/v1/ingest/poll", {
			method: "POST",
			body: payload,
			webSessionToken: options?.webSessionToken,
			writeAccessToken: options?.writeAccessToken,
		});
	},

	getIngestRun(runId: string) {
		const safeId = encodeURIComponent(assertSafeIdentifier(runId));
		return requestJson<IngestRun>(`/api/v1/ingest/runs/${safeId}`);
	},

	judgeConsumptionBatch(
		batchId: string,
		options?: {
			webSessionToken?: string | null;
			writeAccessToken?: string | null;
		},
	) {
		const safeId = encodeURIComponent(assertSafeIdentifier(batchId));
		return requestJson<ClusterVerdictManifest>(
			`/api/v1/reader/batches/${safeId}/judge`,
			{
				method: "POST",
				webSessionToken: options?.webSessionToken,
				writeAccessToken: options?.writeAccessToken,
			},
		);
	},

	getClusterVerdictManifest(batchId: string) {
		const safeId = encodeURIComponent(assertSafeIdentifier(batchId));
		return requestJson<ClusterVerdictManifest>(
			`/api/v1/reader/batches/${safeId}/manifest`,
		);
	},

	materializeConsumptionBatch(
		batchId: string,
		options?: {
			webSessionToken?: string | null;
			writeAccessToken?: string | null;
		},
	) {
		const safeId = encodeURIComponent(assertSafeIdentifier(batchId));
		return requestJson<ReaderBatchMaterialization>(
			`/api/v1/reader/batches/${safeId}/materialize`,
			{
				method: "POST",
				webSessionToken: options?.webSessionToken,
				writeAccessToken: options?.writeAccessToken,
			},
		);
	},

	listPublishedReaderDocuments(params?: {
		limit?: number;
		window_id?: string;
	}) {
		return requestJson<ReaderDocument[]>("/api/v1/reader/documents", {}, params);
	},

	getPublishedReaderDocument(documentId: string) {
		const safeId = encodeURIComponent(assertSafeIdentifier(documentId));
		return requestJson<ReaderDocument>(`/api/v1/reader/documents/${safeId}`);
	},

	repairPublishedReaderDocument(
		documentId: string,
		payload: ReaderDocumentRepairRequest,
		options?: {
			webSessionToken?: string | null;
			writeAccessToken?: string | null;
		},
	) {
		const safeId = encodeURIComponent(assertSafeIdentifier(documentId));
		return requestJson<ReaderDocument>(`/api/v1/reader/documents/${safeId}/repair`, {
			method: "POST",
			body: payload,
			webSessionToken: options?.webSessionToken,
			writeAccessToken: options?.writeAccessToken,
		});
	},

	getNavigationBrief(params?: { window_id?: string; limit?: number }) {
		return requestJson<NavigationBrief>(
			"/api/v1/reader/navigation-brief",
			{},
			params,
		);
	},

	listIngestRuns(params?: {
		status?: string;
		platform?: Platform;
		limit?: number;
	}) {
		return requestJson<IngestRunSummary[]>("/api/v1/ingest/runs", {}, params);
	},

	listVideos(params?: {
		platform?: Platform;
		status?: JobStatus;
		limit?: number;
	}) {
		return requestJson<Video[]>("/api/v1/videos", {}, params);
	},

	processVideo(
		payload: VideoProcessRequest,
		options?: { writeAccessToken?: string | null },
	) {
		return requestJson<VideoProcessResponse>("/api/v1/videos/process", {
			method: "POST",
			body: payload,
			writeAccessToken: options?.writeAccessToken,
		});
	},

	getJob(jobId: string) {
		const safeJobId = encodeURIComponent(assertSafeIdentifier(jobId));
		return requestJson<Job>(`/api/v1/jobs/${safeJobId}`).then(normalizeJob);
	},

	getJobCompare(jobId: string) {
		const safeJobId = encodeURIComponent(assertSafeIdentifier(jobId));
		return requestJson<JobCompare>(`/api/v1/jobs/${safeJobId}/compare`);
	},

	getJobEvidenceBundle(jobId: string) {
		const safeJobId = encodeURIComponent(assertSafeIdentifier(jobId));
		return requestJson<JobEvidenceBundle>(`/api/v1/jobs/${safeJobId}/bundle`);
	},

	getJobKnowledgeCards(jobId: string) {
		const safeJobId = encodeURIComponent(assertSafeIdentifier(jobId));
		return requestJson<KnowledgeCard[]>(
			`/api/v1/jobs/${safeJobId}/knowledge-cards`,
			{},
			undefined,
			normalizeKnowledgeCards,
		);
	},

	listKnowledgeCards(params?: {
		job_id?: string;
		video_id?: string;
		card_type?: string;
		topic_key?: string;
		claim_kind?: string;
		limit?: number;
	}) {
		return requestJson<KnowledgeCard[]>(
			"/api/v1/knowledge/cards",
			{},
			params,
			normalizeKnowledgeCards,
		);
	},

	searchRetrieval(payload: {
		query: string;
		top_k?: number;
		mode?: RetrievalSearchMode;
		filters?: Record<string, string>;
	}) {
		return requestJson<RetrievalSearchResponse>(
			"/api/v1/retrieval/search",
			{
				method: "POST",
				body: {
					query: payload.query,
					top_k: payload.top_k ?? 8,
					mode: payload.mode ?? "keyword",
					filters: payload.filters ?? {},
				},
			},
			undefined,
			normalizeRetrievalSearchResponse,
		);
	},

	async getAskAnswer(payload: {
		question?: string;
		watchlist_id?: string;
		story_id?: string;
		topic_key?: string;
		top_k?: number;
		mode?: RetrievalSearchMode;
	}) {
		const safeQuestion = payload.question?.trim() ?? "";
		const safeWatchlistId = payload.watchlist_id?.trim() ?? "";
		const safeStoryId = payload.story_id?.trim() ?? "";
		const safeTopicKey = payload.topic_key?.trim() ?? "";
		const safeMode = normalizeRetrievalMode(payload.mode);
		const safeTopK = normalizeTopK(payload.top_k, 6);
		return requestJson<AskAnswerResponse>("/api/v1/retrieval/answer/page", {
			method: "POST",
			body: {
				query: safeQuestion,
				watchlist_id: safeWatchlistId || undefined,
				story_id: safeStoryId || undefined,
				topic_key: safeTopicKey || undefined,
				top_k: safeTopK,
				mode: safeMode,
				filters: {},
			},
		});
	},

	getArtifactMarkdown,

	getNotificationConfig() {
		return requestJson<NotificationConfig>("/api/v1/notifications/config");
	},

	getOpsInbox(params?: { limit?: number; window_hours?: number }) {
		return requestJson<OpsInboxResponse>("/api/v1/ops/inbox", {}, params);
	},

	listWatchlists() {
		return requestJson<Watchlist[]>("/api/v1/watchlists");
	},

	upsertWatchlist(
		payload: WatchlistUpsertRequest,
		options?: { writeAccessToken?: string | null },
	) {
		return requestJson<Watchlist>("/api/v1/watchlists", {
			method: "POST",
			body: payload,
			writeAccessToken: options?.writeAccessToken,
		});
	},

	deleteWatchlist(
		watchlistId: string,
		options?: { writeAccessToken?: string | null },
	) {
		const safeId = encodeURIComponent(assertSafeIdentifier(watchlistId));
		return requestJson<void>(`/api/v1/watchlists/${safeId}`, {
			method: "DELETE",
			writeAccessToken: options?.writeAccessToken,
		});
	},

	getWatchlistTrend(
		watchlistId: string,
		params?: { limit_runs?: number; limit_cards?: number },
	) {
		const safeId = encodeURIComponent(assertSafeIdentifier(watchlistId));
		return requestJson<WatchlistTrendResponse>(
			`/api/v1/watchlists/${safeId}/trend`,
			{},
			params,
		);
	},

	getWatchlistBriefing(
		watchlistId: string,
		params?: {
			limit_runs?: number;
			limit_cards?: number;
			limit_stories?: number;
			limit_evidence_per_story?: number;
		},
	) {
		const safeId = encodeURIComponent(assertSafeIdentifier(watchlistId));
		return requestJson<WatchlistBriefing>(
			`/api/v1/watchlists/${safeId}/briefing`,
			{},
			params,
		);
	},

	getWatchlistBriefingPage(
		watchlistId: string,
		params?: {
			story_id?: string;
			query?: string;
			limit_runs?: number;
			limit_cards?: number;
			limit_stories?: number;
			limit_evidence_per_story?: number;
		},
	) {
		const safeId = encodeURIComponent(assertSafeIdentifier(watchlistId));
		const safeStoryId = params?.story_id?.trim() ?? "";
		const safeQuery = params?.query?.trim() ?? "";
		return requestJson<WatchlistBriefingPage>(
			`/api/v1/watchlists/${safeId}/briefing/page`,
			{},
			{
				...params,
				story_id: safeStoryId || undefined,
				query: safeQuery || undefined,
			},
		);
	},

	updateNotificationConfig(
		payload: NotificationConfigUpdateRequest,
		options?: { writeAccessToken?: string | null },
	) {
		return requestJson<NotificationConfig>("/api/v1/notifications/config", {
			method: "PUT",
			body: payload,
			writeAccessToken: options?.writeAccessToken,
		});
	},

	sendNotificationTest(
		payload: NotificationTestRequest,
		options?: { writeAccessToken?: string | null },
	) {
		return requestJson<NotificationSendResponse>("/api/v1/notifications/test", {
			method: "POST",
			body: payload,
			writeAccessToken: options?.writeAccessToken,
		});
	},

	getDigestFeed(params?: {
		source?: Platform;
		category?: "tech" | "creator" | "macro" | "ops" | "misc";
		feedback?: "saved" | "useful" | "noisy" | "dismissed" | "archived";
		sort?: "recent" | "curated";
		subscription_id?: string;
		limit?: number;
		cursor?: string;
		since?: string;
	}) {
		const query = params
			? {
					...(params as Record<string, unknown>),
					sub: params.subscription_id,
				}
			: undefined;
		if (query && "subscription_id" in query) {
			delete query.subscription_id;
		}
		return requestJson<DigestFeedResponse>(
			"/api/v1/feed/digests",
			{},
			query,
			normalizeDigestFeedResponse,
		);
	},

	getFeedFeedback(jobId: string) {
		const safeJobId = encodeURIComponent(assertSafeIdentifier(jobId));
		return requestJson<FeedFeedback>(
			`/api/v1/feed/feedback?job_id=${safeJobId}`,
		);
	},

	updateFeedFeedback(
		payload: FeedFeedbackUpdateRequest,
		options?: {
			webSessionToken?: string | null;
			writeAccessToken?: string | null;
		},
	) {
		return requestJson<FeedFeedback>("/api/v1/feed/feedback", {
			method: "PUT",
			body: payload,
			webSessionToken: options?.webSessionToken,
			writeAccessToken: options?.writeAccessToken,
		});
	},

	setFeedFeedback(
		payload: FeedFeedbackUpdateRequest,
		options?: {
			webSessionToken?: string | null;
			writeAccessToken?: string | null;
		},
	) {
		return this.updateFeedFeedback(payload, options);
	},
};

function resolveFetch(fetchImpl?: typeof fetch): typeof fetch {
	const candidate = fetchImpl ?? globalThis.fetch;
	if (!candidate) {
		throw new Error("ERR_FETCH_UNAVAILABLE");
	}
	return candidate;
}

function normalizeBaseUrl(baseUrl: string): string {
	const trimmed = baseUrl.trim();
	if (!trimmed) {
		throw new Error("ERR_INVALID_BASE_URL");
	}
	return new URL(trimmed).origin;
}

function buildWriteHeaders(
	clientOptions: SourceHarborClientOptions,
	requestOptions: RequestOptions,
): Headers | undefined {
	const method = requestOptions.method?.trim().toUpperCase() ?? "GET";
	if (method === "GET" || method === "HEAD") {
		return undefined;
	}
	const headers = new Headers(requestOptions.headers ?? {});
	const writeAccessToken =
		requestOptions.writeAccessToken?.trim() ??
		clientOptions.writeAccessToken?.trim();
	const webSessionToken =
		requestOptions.webSessionToken?.trim() ?? clientOptions.webSessionToken?.trim();
	if (writeAccessToken) {
		headers.set("X-API-Key", writeAccessToken);
		headers.set("Authorization", `Bearer ${writeAccessToken}`);
		return headers;
	}
	if (webSessionToken) {
		headers.set("X-Web-Session", webSessionToken);
		return headers;
	}
	return headers;
}

export function createSourceHarborClient(
	clientOptions: SourceHarborClientOptions,
) {
	const fetchImpl = resolveFetch(clientOptions.fetchImpl);
	const baseUrl = normalizeBaseUrl(clientOptions.baseUrl);

	async function requestJsonForBase<T>(
		path: string,
		requestOptions: RequestOptions = {},
		query?: Record<string, string | number | boolean | null | undefined>,
		normalize?: (payload: unknown) => T,
	): Promise<T> {
		const url = buildApiUrlFromBaseUrl(baseUrl, path, query);
		let response: Response;
		try {
			const authHeaders = buildWriteHeaders(clientOptions, requestOptions);
			response = await fetchImpl(url, {
				...requestOptions,
				cache: "no-store",
				headers: (() => {
					const headers = authHeaders ?? new Headers(requestOptions.headers ?? {});
					headers.set("Content-Type", "application/json");
					return headers;
				})(),
				body:
					requestOptions.body === undefined
						? undefined
						: JSON.stringify(requestOptions.body),
			});
		} catch {
			throw new Error("ERR_REQUEST_FAILED");
		}

		if (!response.ok) {
			const reason = await parseError(response);
			throw new Error(reason);
		}

		if (response.status === 204) {
			return undefined as T;
		}

		const textBody = await response.text().catch(() => "");
		if (!textBody.trim()) {
			throw new Error("ERR_PROTOCOL_EMPTY_BODY");
		}

		let parsed: unknown;
		try {
			parsed = JSON.parse(textBody);
		} catch {
			throw new Error("ERR_REQUEST_FAILED");
		}

		if (normalize) {
			return normalize(parsed);
		}
		return parsed as T;
	}

	return {
		listSubscriptionTemplates() {
			return requestJsonForBase<SubscriptionTemplateCatalogResponse>(
				"/api/v1/subscriptions/templates",
			);
		},

			listSubscriptions(params?: {
				platform?: Platform;
				category?: SubscriptionCategory;
				enabled_only?: boolean;
			}) {
				return requestJsonForBase<Subscription[]>("/api/v1/subscriptions", {}, params);
			},

			submitManualSourceIntake(
				payload: ManualSourceIntakeRequest,
				requestOptions?: {
					webSessionToken?: string | null;
					writeAccessToken?: string | null;
				},
			) {
				return requestJsonForBase<ManualSourceIntakeResponse>(
					"/api/v1/subscriptions/manual-intake",
					{
						method: "POST",
						body: payload,
						webSessionToken: requestOptions?.webSessionToken,
						writeAccessToken: requestOptions?.writeAccessToken,
					},
				);
			},

			search(params: {
				query: string;
			topK?: number;
			mode?: RetrievalSearchMode;
			filters?: Record<string, string>;
		}) {
			return this.searchRetrieval({
				query: params.query,
				top_k: params.topK ?? 8,
				mode: params.mode,
				filters: params.filters,
			});
		},

		searchRetrieval(payload: {
			query: string;
			top_k?: number;
			mode?: RetrievalSearchMode;
			filters?: Record<string, string>;
		}) {
			return requestJsonForBase<RetrievalSearchResponse>(
				"/api/v1/retrieval/search",
				{
					method: "POST",
					body: {
						query: payload.query,
						top_k: payload.top_k ?? 8,
						mode: payload.mode ?? "keyword",
						filters: payload.filters ?? {},
					},
				},
				undefined,
				normalizeRetrievalSearchResponse,
			);
		},

		getAskAnswerPage(payload: {
			question?: string;
			watchlist_id?: string;
			story_id?: string;
			topic_key?: string;
			top_k?: number;
			mode?: RetrievalSearchMode;
		}) {
			return requestJsonForBase<AskAnswerResponse>(
				"/api/v1/retrieval/answer/page",
				{
					method: "POST",
					body: {
						query: payload.question?.trim() ?? "",
						watchlist_id: payload.watchlist_id?.trim() || undefined,
						story_id: payload.story_id?.trim() || undefined,
						topic_key: payload.topic_key?.trim() || undefined,
						top_k: payload.top_k ?? 6,
						mode: payload.mode ?? "keyword",
						filters: {},
					},
				},
			);
		},

		getJob(jobId: string) {
			const safeJobId = encodeURIComponent(assertSafeIdentifier(jobId));
			return requestJsonForBase<Job>(`/api/v1/jobs/${safeJobId}`).then(normalizeJob);
		},

		getJobCompare(jobId: string) {
			const safeJobId = encodeURIComponent(assertSafeIdentifier(jobId));
			return requestJsonForBase<JobCompare>(
				`/api/v1/jobs/${safeJobId}/compare`,
			);
		},

		getJobEvidenceBundle(jobId: string) {
			const safeJobId = encodeURIComponent(assertSafeIdentifier(jobId));
			return requestJsonForBase<JobEvidenceBundle>(
				`/api/v1/jobs/${safeJobId}/bundle`,
			);
		},

		listWatchlists() {
			return requestJsonForBase<Watchlist[]>("/api/v1/watchlists");
		},

		getWatchlistBriefingPage(
			watchlistId: string,
			params?: {
				story_id?: string;
				query?: string;
				limit_runs?: number;
				limit_cards?: number;
				limit_stories?: number;
				limit_evidence_per_story?: number;
			},
		) {
			const safeId = encodeURIComponent(assertSafeIdentifier(watchlistId));
			return requestJsonForBase<WatchlistBriefingPage>(
				`/api/v1/watchlists/${safeId}/briefing/page`,
				{},
				{
					...params,
					story_id: params?.story_id?.trim() || undefined,
					query: params?.query?.trim() || undefined,
				},
			);
		},

		getOpsInbox(params?: { limit?: number; window_hours?: number }) {
			return requestJsonForBase<OpsInboxResponse>("/api/v1/ops/inbox", {}, params);
		},

		pollIngest(
			payload: IngestPollRequest,
			requestOptions?: {
				webSessionToken?: string | null;
				writeAccessToken?: string | null;
			},
		) {
			return requestJsonForBase<IngestPollResponse>("/api/v1/ingest/poll", {
				method: "POST",
				body: payload,
				webSessionToken: requestOptions?.webSessionToken,
				writeAccessToken: requestOptions?.writeAccessToken,
			});
		},

		judgeConsumptionBatch(
			batchId: string,
			requestOptions?: {
				webSessionToken?: string | null;
				writeAccessToken?: string | null;
			},
		) {
			const safeId = encodeURIComponent(assertSafeIdentifier(batchId));
			return requestJsonForBase<ClusterVerdictManifest>(
				`/api/v1/reader/batches/${safeId}/judge`,
				{
					method: "POST",
					webSessionToken: requestOptions?.webSessionToken,
					writeAccessToken: requestOptions?.writeAccessToken,
				},
			);
		},

		getClusterVerdictManifest(batchId: string) {
			const safeId = encodeURIComponent(assertSafeIdentifier(batchId));
			return requestJsonForBase<ClusterVerdictManifest>(
				`/api/v1/reader/batches/${safeId}/manifest`,
			);
		},

		materializeConsumptionBatch(
			batchId: string,
			requestOptions?: {
				webSessionToken?: string | null;
				writeAccessToken?: string | null;
			},
		) {
			const safeId = encodeURIComponent(assertSafeIdentifier(batchId));
			return requestJsonForBase<ReaderBatchMaterialization>(
				`/api/v1/reader/batches/${safeId}/materialize`,
				{
					method: "POST",
					webSessionToken: requestOptions?.webSessionToken,
					writeAccessToken: requestOptions?.writeAccessToken,
				},
			);
		},

		listPublishedReaderDocuments(params?: {
			limit?: number;
			window_id?: string;
		}) {
			return requestJsonForBase<ReaderDocument[]>(
				"/api/v1/reader/documents",
				{},
				params,
			);
		},

		getPublishedReaderDocument(documentId: string) {
			const safeId = encodeURIComponent(assertSafeIdentifier(documentId));
			return requestJsonForBase<ReaderDocument>(`/api/v1/reader/documents/${safeId}`);
		},

		repairPublishedReaderDocument(
			documentId: string,
			payload: ReaderDocumentRepairRequest,
			requestOptions?: {
				webSessionToken?: string | null;
				writeAccessToken?: string | null;
			},
		) {
			const safeId = encodeURIComponent(assertSafeIdentifier(documentId));
			return requestJsonForBase<ReaderDocument>(
				`/api/v1/reader/documents/${safeId}/repair`,
				{
					method: "POST",
					body: payload,
					webSessionToken: requestOptions?.webSessionToken,
					writeAccessToken: requestOptions?.writeAccessToken,
				},
			);
		},

		getNavigationBrief(params?: { window_id?: string; limit?: number }) {
			return requestJsonForBase<NavigationBrief>(
				"/api/v1/reader/navigation-brief",
				{},
				params,
			);
		},

		processVideo(
			payload: VideoProcessRequest,
			requestOptions?: { writeAccessToken?: string | null },
		) {
			return requestJsonForBase<VideoProcessResponse>(
				"/api/v1/videos/process",
				{
					method: "POST",
					body: payload,
					writeAccessToken: requestOptions?.writeAccessToken,
				},
			);
		},

		buildArtifactAssetUrl(jobId: string, path: string) {
			return buildArtifactAssetUrlFromBaseUrl(baseUrl, jobId, path);
		},
	};
}
