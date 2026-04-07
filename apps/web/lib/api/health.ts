import * as http from "node:http";
import * as https from "node:https";

import { buildApiUrl } from "@/lib/api/url";

export type ApiHealthState = "healthy" | "unhealthy" | "timeout_or_unknown";

type ProbeOptions = {
	timeoutMs?: number;
};

export async function fetchApiHealthState(
	options: ProbeOptions = {},
): Promise<ApiHealthState> {
	const timeoutMs = options.timeoutMs ?? 2000;
	const target = new URL(buildApiUrl("/healthz"));
	const requestImpl =
		target.protocol === "https:" ? https.request : http.request;

	return await new Promise<ApiHealthState>((resolve) => {
		const req = requestImpl(
			target,
			{
				method: "GET",
				headers: { Accept: "application/json" },
			},
			(res) => {
				res.resume();
				resolve((res.statusCode ?? 500) < 400 ? "healthy" : "unhealthy");
			},
		);

		req.setTimeout(timeoutMs, () => {
			req.destroy(new Error("api_health_timeout"));
		});
		req.on("error", () => resolve("timeout_or_unknown"));
		req.end();
	});
}
