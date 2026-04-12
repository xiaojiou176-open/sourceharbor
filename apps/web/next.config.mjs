import path from "node:path";
import { fileURLToPath } from "node:url";

const configDir = path.dirname(fileURLToPath(import.meta.url));
const monorepoRoot = path.resolve(configDir, "../..");

/** @type {import('next').NextConfig} */
const nextConfig = {
	reactStrictMode: true,
	experimental: {
		externalDir: true,
	},
	images: {
		remotePatterns: [
			{
				protocol: "https",
				hostname: "i.ytimg.com",
			},
		],
	},
	outputFileTracingRoot: monorepoRoot,
	transpilePackages: ["@sourceharbor/sdk"],
	turbopack: {
		root: configDir,
	},
	...(process.env.WEB_E2E_NEXT_DIST_DIR
		? { distDir: process.env.WEB_E2E_NEXT_DIST_DIR }
		: {}),
};

export default nextConfig;
