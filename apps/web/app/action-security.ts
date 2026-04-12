import crypto from "node:crypto";

import { cookies } from "next/headers";
import { z } from "zod";
import { sanitizeExternalUrl } from "@/lib/api/url";

const MAX_TEXT_LENGTH = 512;
const SESSION_COOKIE_NAME = "sourceharbor_web_session";
const SESSION_TOKEN_TTL_SECONDS = 15 * 60;

const identifierSchema = z
	.string()
	.trim()
	.min(1)
	.max(128)
	.regex(/^[A-Za-z0-9][A-Za-z0-9._:-]*$/);
const httpUrlSchema = z
	.string()
	.trim()
	.url()
	.max(MAX_TEXT_LENGTH)
	.refine((value) => sanitizeExternalUrl(value) !== null, {
		message: "ERR_INVALID_INPUT",
	});
const nullableEmailSchema = z.preprocess((value) => {
	if (value === null || value === undefined) {
		return null;
	}
	if (typeof value === "string" && value.trim().length === 0) {
		return null;
	}
	return value;
}, z.string().trim().email().max(MAX_TEXT_LENGTH).nullable());
const nullableHourSchema = z.preprocess((value) => {
	if (value === null || value === undefined) {
		return null;
	}
	if (typeof value === "string" && value.trim().length === 0) {
		return null;
	}
	return value;
}, z.coerce.number().int().min(0).max(23).nullable());

function getSessionSecret(): string {
	return (
		process.env.WEB_ACTION_SESSION_TOKEN ??
		process.env.NEXT_PUBLIC_WEB_ACTION_SESSION_TOKEN ??
		process.env.SOURCE_HARBOR_API_KEY ??
		""
	).trim();
}

function constantTimeEquals(left: string, right: string): boolean {
	const leftBuffer = Buffer.from(left);
	const rightBuffer = Buffer.from(right);
	if (leftBuffer.length !== rightBuffer.length) {
		return false;
	}
	return crypto.timingSafeEqual(leftBuffer, rightBuffer);
}

function isSessionEnforcementEnabled(): boolean {
	return getSessionSecret().length > 0;
}

function tokenBucket(nowMs: number = Date.now()): number {
	return Math.floor(nowMs / 1000 / SESSION_TOKEN_TTL_SECONDS);
}

function signSessionBucket(secret: string, bucket: number): string {
	return crypto
		.createHmac("sha256", secret)
		.update(String(bucket))
		.digest("hex");
}

function buildSignedSessionToken(
	secret: string,
	bucket: number = tokenBucket(),
): string {
	return `${bucket}.${signSessionBucket(secret, bucket)}`;
}

function isValidSignedSessionToken(secret: string, candidate: string): boolean {
	const parts = candidate.split(".");
	if (parts.length !== 2) {
		return false;
	}

	const [bucketRaw, signatureRaw] = parts;
	if (!/^\d+$/.test(bucketRaw) || !/^[a-f0-9]{64}$/i.test(signatureRaw)) {
		return false;
	}

	const bucket = Number.parseInt(bucketRaw, 10);
	const currentBucket = tokenBucket();
	if (bucket > currentBucket + 1 || currentBucket - bucket > 1) {
		return false;
	}

	const expectedSignature = signSessionBucket(secret, bucket);
	return constantTimeEquals(expectedSignature, signatureRaw.toLowerCase());
}

async function readSessionCandidate(formData: FormData): Promise<string> {
	const cookieStore = await cookies();
	const cookieToken = cookieStore.get(SESSION_COOKIE_NAME)?.value?.trim();
	const formToken = String(formData.get("session_token") ?? "").trim();
	return cookieToken || formToken;
}

export async function assertActionSession(formData: FormData): Promise<void> {
	if (!isSessionEnforcementEnabled()) {
		return;
	}
	const expected = getSessionSecret();
	const actual = await readSessionCandidate(formData);
	if (!actual) {
		return;
	}

	if (isValidSignedSessionToken(expected, actual)) {
		return;
	}

	// Backward compatibility: allow legacy raw token cookies during rollout.
	if (!constantTimeEquals(expected, actual)) {
		throw new Error("ERR_AUTH_REQUIRED");
	}
}

export function getActionSessionTokenForForm(): string {
	const secret = getSessionSecret();
	return secret ? buildSignedSessionToken(secret) : "";
}

export function parseIdentifier(raw: unknown): string {
	const result = identifierSchema.safeParse(raw);
	if (!result.success) {
		throw new Error("ERR_INVALID_IDENTIFIER");
	}
	return result.data;
}

export function safeEncodeIdentifier(raw: unknown): string {
	return encodeURIComponent(parseIdentifier(raw));
}

export function toActionErrorCode(error: unknown): string {
	if (error instanceof z.ZodError) {
		for (const issue of error.issues) {
			const normalizedMessage =
				issue.message.trim().toUpperCase().split(":")[0] ?? "";
			if (normalizedMessage.startsWith("ERR_")) {
				return normalizedMessage;
			}

			const path = issue.path
				.filter((segment): segment is string => typeof segment === "string")
				.map((segment) => segment.toLowerCase());
			if (
				path.some((segment) => segment === "url" || segment.endsWith("_url"))
			) {
				return "ERR_INVALID_URL";
			}
			if (
				path.some(
					(segment) => segment === "email" || segment.endsWith("_email"),
				)
			) {
				return "ERR_INVALID_EMAIL";
			}
			if (
				path.some(
					(segment) => segment === "identifier" || segment.endsWith("_id"),
				)
			) {
				return "ERR_INVALID_IDENTIFIER";
			}
		}
		return "ERR_INVALID_INPUT";
	}
	if (error instanceof Error) {
		const normalized = error.message.trim().toUpperCase().split(":")[0] ?? "";
		if (normalized.startsWith("ERR_")) {
			return normalized;
		}
	}
	return "ERR_REQUEST_FAILED";
}

export function isNextRedirectError(error: unknown): boolean {
	return (
		error instanceof Error &&
		typeof (error as Error & { digest?: unknown }).digest === "string" &&
		(error as Error & { digest: string }).digest.startsWith("NEXT_REDIRECT")
	);
}

export const schemas = {
	pollIngest: z.object({
		platform: z.enum(["youtube", "bilibili"]).optional(),
		max_new_videos: z.coerce.number().int().min(1).max(500).default(50),
	}),
	processVideo: z.object({
		platform: z.enum(["youtube", "bilibili"]),
		url: httpUrlSchema,
		mode: z
			.enum(["full", "text_only", "refresh_comments", "refresh_llm"])
			.default("full"),
		force: z.boolean().default(false),
	}),
	subscriptionUpsert: z.object({
		platform: z.string().trim().min(1).max(MAX_TEXT_LENGTH),
		source_type: z.string().trim().min(1).max(MAX_TEXT_LENGTH),
		source_value: z.string().trim().min(1).max(MAX_TEXT_LENGTH),
		adapter_type: z.enum(["rsshub_route", "rss_generic"]),
		source_url: httpUrlSchema.nullable(),
		rsshub_route: z.string().trim().max(MAX_TEXT_LENGTH).nullable(),
		category: z.enum(["misc", "tech", "creator", "macro", "ops"]),
		tags: z.array(z.string().trim().min(1).max(64)).max(20),
		priority: z.coerce.number().int().min(0).max(100).default(50),
		enabled: z.boolean().default(false),
	}),
	notificationConfig: z
		.object({
			enabled: z.boolean().default(false),
			to_email: nullableEmailSchema,
			daily_digest_enabled: z.boolean().default(false),
			daily_digest_hour_utc: nullableHourSchema,
			failure_alert_enabled: z.boolean().default(false),
		})
		.superRefine((value, context) => {
			if (value.enabled && value.to_email === null) {
				context.addIssue({
					code: z.ZodIssueCode.custom,
					path: ["to_email"],
					message: "ERR_NOTIFICATION_EMAIL_REQUIRED",
				});
			}
			if (value.daily_digest_enabled && value.daily_digest_hour_utc === null) {
				context.addIssue({
					code: z.ZodIssueCode.custom,
					path: ["daily_digest_hour_utc"],
					message: "ERR_DAILY_DIGEST_HOUR_REQUIRED",
				});
			}
		}),
	notificationTest: z.object({
		to_email: z.string().trim().email().max(MAX_TEXT_LENGTH).nullable(),
		subject: z.string().trim().max(MAX_TEXT_LENGTH).nullable(),
		body: z.string().trim().max(4000).nullable(),
	}),
};
