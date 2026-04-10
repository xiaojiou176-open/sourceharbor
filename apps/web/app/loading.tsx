import { LoadingStateCard } from "@/components/loading-state-card";
import { getLocaleMessages } from "@/lib/i18n/messages";

export default function AppLoading() {
	const copy = getLocaleMessages().loading.app;
	return (
		<>
			<h1 className="sr-only">{copy.title}</h1>
			<LoadingStateCard
				title={copy.title}
				message={copy.message}
				messageId="app-loading-message"
			/>
		</>
	);
}
