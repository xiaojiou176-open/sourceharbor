import {
	buildApiUrlFromBaseUrl,
	buildArtifactAssetUrlFromBaseUrl,
	isSensitiveQueryKey,
	type QueryValue,
	sanitizeExternalUrl,
} from "@sourceharbor/sdk";

type ResolveOptions = {
	allowFallback?: boolean;
	strict?: boolean;
};

function resolveLocalApiBaseUrl(): string {
	const configuredPort = process.env.API_PORT?.trim();
	if (configuredPort && /^\d+$/.test(configuredPort)) {
		return `http://127.0.0.1:${configuredPort}`;
	}
	return "http://127.0.0.1:9000";
}

export function resolveApiBaseUrl(options: ResolveOptions = {}): string {
	const strict = options.strict === true;
	const allowFallback = strict ? false : (options.allowFallback ?? true);
	const rawBase = process.env.NEXT_PUBLIC_API_BASE_URL;
	const base = rawBase?.trim();
	if (!base) {
		if (allowFallback) {
			return resolveLocalApiBaseUrl();
		}
		throw new Error(
			"API base URL is not configured. Set NEXT_PUBLIC_API_BASE_URL.",
		);
	}

	let parsed: URL;
	try {
		parsed = new URL(base);
	} catch {
		throw new Error(
			`Invalid API base URL '${base}'. NEXT_PUBLIC_API_BASE_URL must be an absolute http(s) URL.`,
		);
	}

	if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
		throw new Error(
			`Invalid API base URL protocol '${parsed.protocol}'. Use http:// or https://.`,
		);
	}

	if (parsed.username || parsed.password) {
		throw new Error(
			"Invalid API base URL credentials. Do not include username/password.",
		);
	}

	if (parsed.search || parsed.hash) {
		throw new Error("Invalid API base URL suffix. Query/hash is not allowed.");
	}

	if (parsed.pathname !== "/" && parsed.pathname !== "") {
		throw new Error(
			"Invalid API base URL path. Use bare origin like https://api.example.com.",
		);
	}

	return parsed.origin;
}

export function buildApiUrl(
	path: string,
	query?: Record<string, QueryValue>,
): string {
	return buildApiUrlFromBaseUrl(resolveApiBaseUrl(), path, query);
}

export function buildApiUrlWithOptions(
	path: string,
	query?: Record<string, QueryValue>,
	resolveOptions: ResolveOptions = {},
): string {
	return buildApiUrlFromBaseUrl(resolveApiBaseUrl(resolveOptions), path, query);
}

export function buildArtifactAssetUrl(jobId: string, path: string): string {
	return buildArtifactAssetUrlFromBaseUrl(resolveApiBaseUrl(), jobId, path);
}

export function getWebActionSessionToken(): string {
	return (
		process.env.WEB_ACTION_SESSION_TOKEN ??
		process.env.NEXT_PUBLIC_WEB_ACTION_SESSION_TOKEN ??
		process.env.SOURCE_HARBOR_API_KEY ??
		""
	).trim();
}

export function resolveWriteSessionToken(
	sessionToken?: string | null,
): string | null {
	const explicit = String(sessionToken ?? "").trim();
	if (explicit) {
		return explicit;
	}
	const fallback = getWebActionSessionToken();
	return fallback || null;
}

export { isSensitiveQueryKey, sanitizeExternalUrl };
