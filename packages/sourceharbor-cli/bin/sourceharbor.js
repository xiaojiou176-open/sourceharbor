#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import process from "node:process";

const DOCS_URL = "https://xiaojiou176-open.github.io/SourceHarbor/";

function resolveApiBaseUrl() {
	const candidates = [
		process.env.SOURCEHARBOR_API_BASE_URL,
		process.env.SOURCE_HARBOR_API_BASE_URL,
		process.env.NEXT_PUBLIC_API_BASE_URL,
		"http://127.0.0.1:9000",
	];
	for (const candidate of candidates) {
		const value = candidate?.trim();
		if (!value) {
			continue;
		}
		try {
			return new URL(value).origin;
		} catch {
			continue;
		}
	}
	throw new Error("Missing valid SourceHarbor API base URL");
}

function buildUrl(baseUrl, path, query = undefined) {
	const url = new URL(path, baseUrl);
	if (query) {
		for (const [key, value] of Object.entries(query)) {
			if (value === null || value === undefined || value === "") {
				continue;
			}
			url.searchParams.set(key, String(value));
		}
	}
	return url;
}

async function requestJson({ baseUrl, path, method = "GET", body }) {
	const response = await fetch(buildUrl(baseUrl, path), {
		method,
		headers: {
			"Content-Type": "application/json",
		},
		body: body === undefined ? undefined : JSON.stringify(body),
	});
	const text = await response.text();
	if (!response.ok) {
		throw new Error(`${response.status} ${text || response.statusText}`);
	}
	return text ? JSON.parse(text) : null;
}

function printJson(value) {
	console.log(JSON.stringify(value, null, 2));
}

function isRepoRoot(candidate) {
	return existsSync(join(candidate, "bin", "sourceharbor"));
}

function findRepoRoot(startDir) {
	let current = resolve(startDir);
	while (true) {
		if (isRepoRoot(current)) {
			return current;
		}
		const parent = dirname(current);
		if (parent === current) {
			return null;
		}
		current = parent;
	}
}

function resolveRepoRoot() {
	const envRoot = process.env.SOURCEHARBOR_REPO_ROOT?.trim();
	if (envRoot && isRepoRoot(envRoot)) {
		return resolve(envRoot);
	}
	return findRepoRoot(process.cwd());
}

function printHelp(repoRoot) {
	const modeLine = repoRoot
		? `Mode: repo-aware delegate (using ${repoRoot}/bin/sourceharbor)`
		: "Mode: public guidance only (no SourceHarbor repo checkout detected)";
	const delegateLine = repoRoot
		? "Delegated commands: bootstrap, up, down, status, full-stack, mcp, doctor, smoke"
		: "Delegated commands are available after you run this inside a SourceHarbor checkout or set SOURCEHARBOR_REPO_ROOT.";

	console.log(`SourceHarbor CLI

Thin public CLI for the SourceHarbor repo-local command surface.
${modeLine}

Commands:
  help          Show this message.
  where         Print the detected SourceHarbor repo root, if any.
  docs          Print the public docs URL.
  templates     Fetch the public subscriptions template catalog from the HTTP API.
  search        Run retrieval search against the HTTP API.
  ask           Run the grounded Ask page contract against the HTTP API.
  job           Fetch one job payload from the HTTP API.
  bootstrap     Delegate to repo-local bin/sourceharbor bootstrap.
  up            Delegate to repo-local bin/sourceharbor up.
  down          Delegate to repo-local bin/sourceharbor down.
  status        Delegate to repo-local bin/sourceharbor status.
  full-stack    Delegate to repo-local bin/sourceharbor full-stack.
  mcp           Delegate to repo-local bin/sourceharbor mcp.
  doctor        Delegate to repo-local bin/sourceharbor doctor.
  smoke         Delegate to repo-local bin/sourceharbor smoke.

${delegateLine}

Examples:
  npm install --global ./packages/sourceharbor-cli
  cd /path/to/sourceharbor
  sourceharbor help
  sourceharbor templates
  sourceharbor search "agent workflows"
  sourceharbor ask "What changed this week?"
  sourceharbor mcp
  sourceharbor docs`);
}

function printMissingRepoGuidance() {
	console.error(
		[
			"SourceHarbor CLI could not find a repo checkout to delegate into.",
			"Run this command inside a SourceHarbor repo, or set SOURCEHARBOR_REPO_ROOT=/path/to/sourceharbor.",
			`Docs: ${DOCS_URL}`,
		].join("\n"),
	);
	process.exit(2);
}

const repoRoot = resolveRepoRoot();
const command = process.argv[2] ?? "help";
const passthroughArgs = process.argv.slice(3);

if (command === "help" || command === "--help" || command === "-h") {
	printHelp(repoRoot);
	process.exit(0);
}

if (command === "where") {
	if (repoRoot) {
		console.log(repoRoot);
		process.exit(0);
	}
	console.log("not-found");
	process.exit(1);
}

if (command === "docs") {
	console.log(DOCS_URL);
	process.exit(0);
}

if (command === "templates") {
	try {
		const payload = await requestJson({
			baseUrl: resolveApiBaseUrl(),
			path: "/api/v1/subscriptions/templates",
		});
		printJson(payload);
		process.exit(0);
	} catch (error) {
		console.error(String(error));
		process.exit(1);
	}
}

if (command === "search") {
	const query = passthroughArgs.join(" ").trim();
	if (!query) {
		console.error("Usage: sourceharbor search <query>");
		process.exit(2);
	}
	try {
		const payload = await requestJson({
			baseUrl: resolveApiBaseUrl(),
			path: "/api/v1/retrieval/search",
			method: "POST",
			body: {
				query,
				mode: "keyword",
				top_k: 5,
				filters: {},
			},
		});
		printJson(payload);
		process.exit(0);
	} catch (error) {
		console.error(String(error));
		process.exit(1);
	}
}

if (command === "ask") {
	const query = passthroughArgs.join(" ").trim();
	if (!query) {
		console.error("Usage: sourceharbor ask <question>");
		process.exit(2);
	}
	try {
		const payload = await requestJson({
			baseUrl: resolveApiBaseUrl(),
			path: "/api/v1/retrieval/answer/page",
			method: "POST",
			body: {
				query,
				mode: "keyword",
				top_k: 6,
				filters: {},
			},
		});
		printJson(payload);
		process.exit(0);
	} catch (error) {
		console.error(String(error));
		process.exit(1);
	}
}

if (command === "job") {
	const jobId = passthroughArgs[0]?.trim();
	if (!jobId) {
		console.error("Usage: sourceharbor job <job_id>");
		process.exit(2);
	}
	try {
		const payload = await requestJson({
			baseUrl: resolveApiBaseUrl(),
			path: `/api/v1/jobs/${encodeURIComponent(jobId)}`,
		});
		printJson(payload);
		process.exit(0);
	} catch (error) {
		console.error(String(error));
		process.exit(1);
	}
}

if (!repoRoot) {
	printMissingRepoGuidance();
}

const delegate = spawnSync(
	join(repoRoot, "bin", "sourceharbor"),
	[command, ...passthroughArgs],
	{
		cwd: process.cwd(),
		stdio: "inherit",
		env: process.env,
	},
);

if (delegate.error) {
	console.error(delegate.error.message);
	process.exit(1);
}

process.exit(delegate.status ?? 1);
