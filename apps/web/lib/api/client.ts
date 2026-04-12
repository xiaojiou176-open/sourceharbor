import {
	createSourceHarborClient,
	apiClient as sdkApiClient,
} from "@sourceharbor/sdk";

import { resolveApiBaseUrl } from "@/lib/api/url";

type WebApiClient = typeof sdkApiClient;

function syncSdkApiBaseUrl(): void {
	if (typeof process === "undefined" || !process.env) {
		return;
	}
	process.env.NEXT_PUBLIC_API_BASE_URL = resolveApiBaseUrl();
}

const methodNames = Object.keys(sdkApiClient) as Array<keyof WebApiClient>;

// Keep the SDK's full method surface, but re-sync the browser-safe app-local API
// origin before each call so client bundles do not fall back to the SDK default
// localhost:9000 when Next public env injection is not visible inside the package.
export const apiClient = Object.fromEntries(
	methodNames.map((methodName) => [
		methodName,
		(...args: unknown[]) => {
			syncSdkApiBaseUrl();
			const method = sdkApiClient[methodName] as (
				...methodArgs: unknown[]
			) => unknown;
			return method(...args);
		},
	]),
) as WebApiClient;

export { createSourceHarborClient };
