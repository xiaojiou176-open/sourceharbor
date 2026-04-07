import { LoadingStateCard } from "@/components/loading-state-card";
import { getLocaleMessages } from "@/lib/i18n/messages";

export default function FeedLoading() {
	const copy = getLocaleMessages().loading.feed;
	return (
		<LoadingStateCard
			title={copy.title}
			message={copy.message}
			messageId="feed-loading-message"
		/>
	);
}
