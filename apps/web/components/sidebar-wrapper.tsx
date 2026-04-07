import { apiClient } from "@/lib/api/client";
import type { Subscription } from "@/lib/api/types";

import { Sidebar } from "./sidebar";

type ApiHealthState = "healthy" | "unhealthy" | "timeout_or_unknown";

type SidebarWrapperProps = {
	apiHealthState: ApiHealthState;
	apiHealthUrl: string;
	apiHealthLabel: string;
};

export async function SidebarWrapper({
	apiHealthState,
	apiHealthUrl,
	apiHealthLabel,
}: SidebarWrapperProps) {
	let subscriptions: Subscription[] = [];
	let subscriptionsLoadError = false;
	try {
		subscriptions = await apiClient.listSubscriptions({ enabled_only: false });
	} catch {
		subscriptionsLoadError = true;
	}
	return (
		<Sidebar
			subscriptions={subscriptions}
			subscriptionsLoadError={subscriptionsLoadError}
			apiHealthState={apiHealthState}
			apiHealthUrl={apiHealthUrl}
			apiHealthLabel={apiHealthLabel}
		/>
	);
}
