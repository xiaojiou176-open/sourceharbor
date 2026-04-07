import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { httpRequestMock, httpsRequestMock } = vi.hoisted(() => ({
	httpRequestMock: vi.fn(),
	httpsRequestMock: vi.fn(),
}));

vi.mock("node:http", () => ({
	request: httpRequestMock,
}));

vi.mock("node:https", () => ({
	request: httpsRequestMock,
}));

import { fetchApiHealthState } from "@/lib/api/health";

function createRequestDouble() {
	const handlers = new Map<string, (value?: unknown) => void>();
	return {
		setTimeout: vi.fn((_ms: number, cb: () => void) => {
			handlers.set("timeout", cb);
		}),
		on: vi.fn((event: string, cb: (value?: unknown) => void) => {
			handlers.set(event, cb);
		}),
		end: vi.fn(),
		destroy: vi.fn((error?: unknown) => {
			handlers.get("error")?.(error);
		}),
		handlers,
	};
}

describe("fetchApiHealthState", () => {
	const envSnapshot = { ...process.env };

	beforeEach(() => {
		vi.clearAllMocks();
		process.env = {
			...envSnapshot,
			NEXT_PUBLIC_API_BASE_URL: "http://127.0.0.1:18000",
		};
	});

	afterEach(() => {
		process.env = { ...envSnapshot };
	});

	it("returns healthy when the upstream responds with 2xx", async () => {
		httpRequestMock.mockImplementation((_url, _options, callback) => {
			callback({ statusCode: 200, resume: vi.fn() });
			return createRequestDouble();
		});

		await expect(fetchApiHealthState({ timeoutMs: 500 })).resolves.toBe(
			"healthy",
		);
	});

	it("returns unhealthy when the upstream responds with >= 400", async () => {
		httpRequestMock.mockImplementation((_url, _options, callback) => {
			callback({ statusCode: 503, resume: vi.fn() });
			return createRequestDouble();
		});

		await expect(fetchApiHealthState({ timeoutMs: 500 })).resolves.toBe(
			"unhealthy",
		);
	});

	it("returns timeout_or_unknown when the request errors", async () => {
		httpRequestMock.mockImplementation(() => {
			const req = createRequestDouble();
			queueMicrotask(() => req.handlers.get("error")?.(new Error("offline")));
			return req;
		});

		await expect(fetchApiHealthState({ timeoutMs: 500 })).resolves.toBe(
			"timeout_or_unknown",
		);
	});

	it("returns timeout_or_unknown when the request times out", async () => {
		httpRequestMock.mockImplementation(() => {
			const req = createRequestDouble();
			queueMicrotask(() => req.handlers.get("timeout")?.());
			return req;
		});

		await expect(fetchApiHealthState({ timeoutMs: 500 })).resolves.toBe(
			"timeout_or_unknown",
		);
	});

	it("uses https transport when NEXT_PUBLIC_API_BASE_URL is https", async () => {
		process.env.NEXT_PUBLIC_API_BASE_URL = "https://api.example.com";
		httpsRequestMock.mockImplementation((_url, _options, callback) => {
			callback({ statusCode: 200, resume: vi.fn() });
			return createRequestDouble();
		});

		await expect(fetchApiHealthState()).resolves.toBe("healthy");
		expect(httpsRequestMock).toHaveBeenCalledTimes(1);
	});

	it("treats missing status code as unhealthy via fallback status", async () => {
		httpRequestMock.mockImplementation((_url, _options, callback) => {
			callback({ resume: vi.fn() });
			return createRequestDouble();
		});

		await expect(fetchApiHealthState({ timeoutMs: 500 })).resolves.toBe(
			"unhealthy",
		);
	});
});
