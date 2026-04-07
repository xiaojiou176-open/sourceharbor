export type SearchParamValue = string | string[] | undefined;
export type SearchParamsRecord = Record<string, SearchParamValue>;
export type SearchParamsInput =
	| SearchParamsRecord
	| Promise<SearchParamsRecord>
	| undefined;

function normalizeParamValue(value: SearchParamValue): string {
	if (Array.isArray(value)) {
		const firstString = value.find((item) => typeof item === "string");
		return firstString?.trim() ?? "";
	}
	return typeof value === "string" ? value.trim() : "";
}

export async function resolveSearchParams<TKeys extends string>(
	searchParams: SearchParamsInput,
	keys: readonly TKeys[],
): Promise<Record<TKeys, string>> {
	const resolved = (await searchParams) ?? {};
	const normalized = {} as Record<TKeys, string>;

	for (const key of keys) {
		normalized[key] = normalizeParamValue(resolved[key]);
	}

	return normalized;
}
