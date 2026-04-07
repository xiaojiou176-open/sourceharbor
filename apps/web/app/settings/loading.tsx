import { LoadingStateCard } from "@/components/loading-state-card";
import { getLocaleMessages } from "@/lib/i18n/messages";

export default function SettingsLoading() {
	const copy = getLocaleMessages().loading.settings;
	return (
		<LoadingStateCard
			title={copy.title}
			message={copy.message}
			messageId="settings-loading-message"
		/>
	);
}
