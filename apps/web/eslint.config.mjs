import { createRequire } from "node:module";
import { defineConfig, globalIgnores } from "eslint/config";
import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypeScript from "eslint-config-next/typescript";

const require = createRequire(import.meta.url);

function eslintMajorVersion() {
	try {
		const { version } = require("eslint/package.json");
		const major = Number.parseInt(String(version).split(".")[0] ?? "", 10);
		return Number.isFinite(major) ? major : 0;
	} catch {
		return 0;
	}
}

const needsEslint10ReactCompatibility = eslintMajorVersion() >= 10;

export default defineConfig([
	...nextCoreWebVitals,
	...nextTypeScript,
	globalIgnores([
		".next/**",
		"**/.next/**",
		".next-e2e-*/**",
		"**/.next-e2e-*/**",
		"out/**",
		"build/**",
		"next-env.d.ts",
	]),
	{
		files: ["**/*.{test,spec}.{ts,tsx}", "**/__tests__/**/*.{ts,tsx}"],
		rules: {
			// expect-expect equivalent: each test case must include an explicit expect call.
			"no-restricted-syntax": [
				"error",
				{
					selector:
						"CallExpression[callee.name=/^(it|test)$/] > :matches(ArrowFunctionExpression, FunctionExpression) > BlockStatement:not(:has(CallExpression[callee.name='expect']))",
					message:
						"Each test must contain at least one explicit expect assertion.",
				},
				{
					selector:
						":matches(IfStatement, ConditionalExpression, SwitchCase, CatchClause) CallExpression[callee.name='expect']",
					message:
						"Avoid conditional expect assertions to prevent false-green tests.",
				},
				{
					selector:
						"CallExpression[callee.object.callee.name='expect'][callee.object.arguments.length=1][callee.object.arguments.0.type='Literal'][callee.property.name=/^(toBe|toEqual|toStrictEqual)$/][arguments.length=1][arguments.0.type='Literal']",
					message:
						"Literal-to-literal assertions are forbidden in tests. Assert business behavior, not constants.",
				},
				{
					selector:
						"CallExpression[callee.object.callee.name='expect'][callee.property.name='toBeDefined'][arguments.length=0]",
					message:
						"`toBeDefined()` is low-value by default. Use stronger assertions or add a documented one-line eslint disable for exceptional cases.",
				},
			],
		},
	},
	{
		rules: {
			// eslint-config-next still enables version-detection rules that use a pre-ESLint-10 context API.
			...(needsEslint10ReactCompatibility
				? {
						"react/display-name": "off",
						"react/no-deprecated": "off",
						"react/no-render-return-value": "off",
						"react/no-string-refs": "off",
					}
				: {}),
			// App Router layout.tsx uses <head> for Google Fonts - Pages Router rule doesn't apply
			"@next/next/no-page-custom-font": "off",
		},
	},
]);
