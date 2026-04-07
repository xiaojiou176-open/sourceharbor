import { LoadingStateCard } from "@/components/loading-state-card";
import { getLocaleMessages } from "@/lib/i18n/messages";

export default function SubscriptionsLoading() {
	const copy = getLocaleMessages().loading.subscriptions;
	return (
		<LoadingStateCard
			title={copy.title}
			message={copy.message}
			messageId="subscriptions-loading-message"
		/>
	);
}
