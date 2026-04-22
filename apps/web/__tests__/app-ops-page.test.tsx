import { render, screen, within } from "@testing-library/react";
import type { AnchorHTMLAttributes, ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import OpsPage from "@/app/ops/page";

const mockGetOpsInbox = vi.fn();

vi.mock("next/link", () => ({
	default: ({
		href,
		children,
		...rest
	}: AnchorHTMLAttributes<HTMLAnchorElement> & {
		href: string;
		children: ReactNode;
	}) => (
		<a href={href} {...rest}>
			{children}
		</a>
	),
}));

vi.mock("@/lib/api/client", () => ({
	apiClient: {
		getOpsInbox: (...args: unknown[]) => mockGetOpsInbox(...args),
	},
}));

describe("ops inbox page", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("renders the ops inbox with aggregated diagnostics", async () => {
		mockGetOpsInbox.mockResolvedValue({
			generated_at: "2026-03-31T10:00:00Z",
			overview: {
				attention_items: 3,
				failed_jobs: 1,
				failed_ingest_runs: 1,
				notification_or_gate_issues: 2,
			},
			failed_jobs: {
				status: "ok",
				total: 1,
				error: null,
				items: [
					{
						id: "job-1",
						title: "AI Weekly",
						platform: "youtube",
						status: "failed",
						pipeline_final_status: "failed",
						error_message: "llm step failed",
						degradation_count: 0,
						updated_at: "2026-03-31T09:30:00Z",
					},
				],
			},
			failed_ingest_runs: {
				status: "ok",
				total: 1,
				error: null,
				items: [],
			},
			notification_deliveries: {
				status: "ok",
				total: 0,
				error: null,
				items: [],
			},
			provider_health: {
				window_hours: 24,
				providers: [
					{
						provider: "gemini",
						ok: 0,
						warn: 1,
						fail: 0,
						last_status: "warn",
						last_checked_at: "2026-03-31T09:40:00Z",
						last_error_kind: "timeout",
						last_message: "Provider timeout",
					},
				],
			},
			gates: {
				retrieval: {
					status: "blocked",
					summary:
						"Retrieval routes are alive, but the current corpus is still effectively empty.",
					next_step: "Seed one real job.",
					details: {},
				},
				notifications: {
					status: "blocked",
					summary:
						"Notification send paths exist, but live delivery is blocked by missing Resend secrets.",
					next_step: "Provide RESEND_API_KEY.",
					details: {},
				},
				disk_governance: {
					status: "warn",
					summary:
						"The repo-side web runtime duplicate is present, but governed cleanup is still blocked by active safety gates.",
					next_step:
						"Keep the duplicate runtime in place until the repo-tmp safety gates clear.",
					details: {},
				},
				ui_audit: {
					status: "ready",
					summary: "Base UI audit is ready today.",
					next_step: "Use a valid artifact root.",
					details: {},
				},
				computer_use: {
					status: "blocked",
					summary:
						"Computer use is implemented, but the live run is currently blocked by a missing Gemini API key.",
					next_step: "Provide GEMINI_API_KEY.",
					details: {},
				},
				bilibili_account_ops: {
					status: "ready",
					summary:
						"Repo-owned Chrome proof and cookie-driven richer read-only lanes are both available.",
					next_step:
						"Use the stronger read-only lanes when you need richer Bilibili evidence.",
					details: {
						login_state: "authenticated",
						cookie_present: true,
					},
				},
			},
			repo_browser_proof: {
				status: "ready",
				summary: "Repo-owned browser proof is current.",
				artifact_path:
					".runtime-cache/reports/runtime/repo-chrome-open-tabs.json",
				generated_at: "2026-04-21T19:40:05Z",
				sites: [
					{
						label: "bilibili_account",
						login_state: "authenticated",
						final_url: "https://account.bilibili.com/account/home",
						proof_kind: "url_page_state",
					},
				],
			},
			inbox_items: [
				{
					kind: "job_failed",
					severity: "critical",
					title: "AI Weekly",
					detail: "llm step failed",
					status_label: "failed",
					last_seen_at: "2026-03-31T09:30:00Z",
					href: "/jobs?job_id=job-1",
					action_label: "Open job",
				},
			],
		});

		render(await OpsPage());

		expect(
			screen.getByRole("heading", { name: "Ops inbox", level: 1 }),
		).toBeInTheDocument();
		expect(
			screen.getByRole("heading", { name: "Ops inbox", level: 3 }),
		).toBeInTheDocument();
		expect(screen.getByText("AI Weekly")).toBeInTheDocument();
		expect(
			screen.getByText(
				/Retrieval routes are alive, but the current corpus is still effectively empty/i,
			),
		).toBeInTheDocument();
		expect(
			screen.getByRole("heading", { name: "Disk governance", level: 3 }),
		).toBeInTheDocument();
		expect(
			screen.getByText(
				/The repo-side web runtime duplicate is present, but governed cleanup is still blocked/i,
			),
		).toBeInTheDocument();
		expect(screen.getByText("Provider timeout")).toBeInTheDocument();
		const inboxSection = screen
			.getByRole("heading", { name: "Ops inbox", level: 3 })
			.closest('[data-slot="card"]');
		expect(inboxSection).not.toBeNull();
		expect(
			within(inboxSection as HTMLElement).getByRole("link", {
				name: "Open job →",
			}),
		).toHaveAttribute("href", "/jobs?job_id=job-1");
		expect(
			screen.getByRole("heading", { name: "Site capability truth", level: 3 }),
		).toBeInTheDocument();
		expect(screen.getByText("YouTube")).toBeInTheDocument();
		expect(
			screen.getByText("Hybrid: Data API + DOM proof"),
		).toBeInTheDocument();
		expect(
			screen.getByRole("heading", {
				name: "Repo-owned browser proof",
				level: 3,
			}),
		).toBeInTheDocument();
		expect(screen.getByText("bilibili_account")).toBeInTheDocument();
		expect(screen.getByText("authenticated")).toBeInTheDocument();
		expect(
			screen.getByText(
				/Repo-owned Chrome proof and cookie-driven richer read-only lanes are both available/i,
			),
		).toBeInTheDocument();
	});
});
