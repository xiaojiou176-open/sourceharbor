import { LoadingStateCard } from "@/components/loading-state-card";
import { getLocaleMessages } from "@/lib/i18n/messages";

export default function JobsLoading() {
	const copy = getLocaleMessages().loading.jobs;
	return (
		<LoadingStateCard
			title={copy.title}
			message={copy.message}
			messageId="jobs-loading-message"
		/>
	);
}
