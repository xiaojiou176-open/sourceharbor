import path from "node:path";
import { defineConfig } from "vitest/config";

const repoRoot = process.env.SOURCE_HARBOR_REPO_ROOT
	? path.resolve(process.env.SOURCE_HARBOR_REPO_ROOT)
	: path.resolve(__dirname, "../..");
const coverageDirectory = path.resolve(
	repoRoot,
	".runtime-cache/reports/web-coverage",
);
const coverageRuntimeDirectory = path.resolve(
	repoRoot,
	".runtime-cache/tmp/vitest-coverage",
);
const coverageSummaryFile = path.relative(
	coverageRuntimeDirectory,
	path.join(coverageDirectory, "coverage-summary.json"),
);

export default defineConfig({
	test: {
		environment: "jsdom",
		globals: true,
		setupFiles: ["./vitest.setup.ts"],
		include: [
			"**/__tests__/**/*.{test,spec}.{ts,tsx}",
			"**/*.{test,spec}.{ts,tsx}",
		],
		exclude: ["node_modules", ".next", "tests/e2e/**"],
		coverage: {
			provider: "v8",
			reportsDirectory: coverageRuntimeDirectory,
			reporter: ["text", ["json-summary", { file: coverageSummaryFile }]],
			include: ["components/**/*.tsx", "lib/**/*.ts"],
			exclude: [
				"**/*.d.ts",
				"tests/**",
				"**/__tests__/**",
				"next-env.d.ts",
				"lib/api/types.ts",
			],
			thresholds: {
				lines: 90,
				functions: 90,
				statements: 90,
				branches: 90,
			},
		},
	},
	resolve: {
		alias: {
			"@": path.resolve(__dirname, "."),
		},
	},
});
