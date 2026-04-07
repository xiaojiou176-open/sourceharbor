import path from "node:path";
import { fileURLToPath } from "node:url";

const configDir = path.dirname(fileURLToPath(import.meta.url));
const runtimeWorkspaceMarker = `${path.sep}.runtime-cache${path.sep}tmp${path.sep}web-runtime${path.sep}workspace${path.sep}apps${path.sep}web`;
const usesManagedRuntimeWorkspace = configDir.includes(runtimeWorkspaceMarker);
const monorepoRoot = usesManagedRuntimeWorkspace
	? path.resolve(configDir, "../..")
	: configDir;

/** @type {import('next').NextConfig} */
const nextConfig = {
	reactStrictMode: true,
	experimental: {
		externalDir: true,
	},
	outputFileTracingRoot: monorepoRoot,
	transpilePackages: ["@sourceharbor/sdk"],
	turbopack: {
		root: monorepoRoot,
	},
	...(process.env.WEB_E2E_NEXT_DIST_DIR
		? { distDir: process.env.WEB_E2E_NEXT_DIST_DIR }
		: {}),
};

export default nextConfig;
