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

// Keep the SDK's full method surface, but resolve it dynamically instead of
// snapshotting method names once. That way newly added SDK methods cannot get
// dropped by the app-local wrapper and turn into server-side page errors.
export const apiClient = new Proxy(sdkApiClient as WebApiClient, {
	get(target, property, receiver) {
		const value = Reflect.get(target, property, receiver);
		if (typeof value !== "function") {
			return value;
		}
		return (...args: unknown[]) => {
			syncSdkApiBaseUrl();
			const method = Reflect.get(target, property, receiver);
			if (typeof method !== "function") {
				return method;
			}
			return method(...args);
		};
	},
}) as WebApiClient;

export { createSourceHarborClient };
