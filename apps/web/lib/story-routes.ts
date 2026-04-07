import type {
	AskStorySelectionBasis,
	RetrievalSearchMode,
	WatchlistBriefing,
	WatchlistBriefingStoryEvidence,
} from "@/lib/api/types";

type AskRouteParams = {
	question?: string | null;
	mode?: RetrievalSearchMode | null;
	top_k?: number | string | null;
};

type BriefingSelectionResult = {
	selectedStory: WatchlistBriefingStoryEvidence | null;
	selectedStoryId: string | null;
	selectionBasis: AskStorySelectionBasis;
};

function normalizeRoute(route: string | null | undefined): string | null {
	const value = route?.trim();
	return value ? value : null;
}

function setParamIfPresent(
	search: URLSearchParams,
	key: string,
	value: string | null | undefined,
): void {
	const safeValue = value?.trim();
	if (safeValue) {
		search.set(key, safeValue);
	}
}

function normalizeSelectionResult(
	story: WatchlistBriefingStoryEvidence | null,
	selectedStoryId: string | null,
	selectionBasis: AskStorySelectionBasis,
): BriefingSelectionResult {
	return {
		selectedStory: story,
		selectedStoryId: selectedStoryId?.trim() || story?.story_id?.trim() || null,
		selectionBasis,
	};
}

export function decorateAskRoute(
	route: string | null | undefined,
	params: AskRouteParams,
): string | null {
	const safeRoute = normalizeRoute(route);
	if (!safeRoute) {
		return null;
	}

	const [withoutHash, hash = ""] = safeRoute.split("#", 2);
	const parsed = new URL(withoutHash, "https://sourceharbor.local");
	setParamIfPresent(parsed.searchParams, "question", params.question);
	setParamIfPresent(parsed.searchParams, "mode", params.mode ?? null);
	if (params.top_k !== null && params.top_k !== undefined) {
		setParamIfPresent(parsed.searchParams, "top_k", String(params.top_k));
	}

	return `${parsed.pathname}${parsed.search}${hash ? `#${hash}` : ""}`;
}

export function preferRoute(
	primary: string | null | undefined,
	fallback: string | null | undefined,
): string | null {
	return normalizeRoute(primary) ?? normalizeRoute(fallback);
}

export function resolveBriefingSelection(
	briefing: WatchlistBriefing | null | undefined,
	requestedStoryId: string | null | undefined,
): BriefingSelectionResult {
	const safeRequestedStoryId = requestedStoryId?.trim() ?? "";
	if (!briefing) {
		return normalizeSelectionResult(null, null, "none");
	}

	const stories = briefing.evidence.stories ?? [];
	const selectedFromServer = briefing.selection?.story ?? null;
	const selectedIdFromServer =
		briefing.selection?.selected_story_id?.trim() ||
		selectedFromServer?.story_id?.trim() ||
		null;
	if (selectedFromServer || selectedIdFromServer) {
		const matchingStory =
			selectedFromServer ??
			stories.find((story) => story.story_id === selectedIdFromServer) ??
			null;
		return normalizeSelectionResult(
			matchingStory,
			selectedIdFromServer,
			briefing.selection?.selection_basis ?? "none",
		);
	}

	const requestedStory =
		stories.find((story) => story.story_id === safeRequestedStoryId) ?? null;
	if (requestedStory) {
		return normalizeSelectionResult(
			requestedStory,
			requestedStory.story_id,
			"requested_story_id",
		);
	}

	const suggestedStory =
		stories.find(
			(story) => story.story_id === briefing.evidence.suggested_story_id,
		) ?? null;
	if (suggestedStory) {
		return normalizeSelectionResult(
			suggestedStory,
			suggestedStory.story_id,
			"suggested_story_id",
		);
	}

	const firstStory = stories[0] ?? null;
	if (firstStory) {
		return normalizeSelectionResult(
			firstStory,
			firstStory.story_id,
			"first_story",
		);
	}

	return normalizeSelectionResult(null, null, "none");
}
