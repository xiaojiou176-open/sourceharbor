import { createSourceHarborClient } from "@sourceharbor/sdk";

const client = createSourceHarborClient({
	baseUrl:
		process.env.SOURCE_HARBOR_API_BASE_URL ??
		`http://127.0.0.1:${process.env.API_PORT ?? "9000"}`,
});

const result = await client.searchRetrieval({
	query: "agent workflows",
	mode: "keyword",
	top_k: 5,
});

console.log(JSON.stringify(result, null, 2));
