import { render, screen, within } from "@testing-library/react";
import type { AnchorHTMLAttributes, ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import BuildersPage from "@/app/builders/page";

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

describe("builders page", () => {
	it("covers builder resource and official-surface CTA labels", () => {
		render(<BuildersPage />);

		expect(
			screen.getByRole("heading", {
				name: "Build with Codex, Claude Code, and MCP clients",
			}),
		).toBeInTheDocument();
		expect(
			screen.getByRole("link", { name: "Inspect Codex bundle" }),
		).toHaveAttribute(
			"href",
			"https://github.com/xiaojiou176-open/sourceharbor/blob/main/starter-packs/codex/sourceharbor-codex-plugin/README.md",
		);
		expect(
			screen.getByRole("link", { name: "Inspect Claude bundle" }),
		).toHaveAttribute(
			"href",
			"https://github.com/xiaojiou176-open/sourceharbor/blob/main/starter-packs/claude-code/sourceharbor-claude-plugin/README.md",
		);
		expect(
			screen.getByRole("link", { name: "Inspect OpenClaw pack" }),
		).toHaveAttribute(
			"href",
			"https://github.com/xiaojiou176-open/sourceharbor/blob/main/starter-packs/openclaw/README.md",
		);
		expect(
			screen.getByRole("link", { name: "Inspect MCP registry template" }),
		).toHaveAttribute(
			"href",
			"https://github.com/xiaojiou176-open/sourceharbor/blob/main/starter-packs/mcp-registry/README.md",
		);
		expect(
			screen.getByRole("link", { name: "Open distribution ledger" }),
		).toHaveAttribute(
			"href",
			"https://github.com/xiaojiou176-open/sourceharbor/blob/main/docs/public-distribution.md",
		);
		expect(
			within(
				screen
					.getByText("What still needs live submission proof")
					.closest("section")!,
			).getByRole("link", { name: "Open current status board" }),
		).toHaveAttribute(
			"href",
			"https://github.com/xiaojiou176-open/sourceharbor/blob/main/docs/project-status.md",
		);
		expect(
			within(
				screen
					.getByText("What still needs live submission proof")
					.closest("section")!,
			).getByRole("link", { name: "Open public skills guide" }),
		).toHaveAttribute(
			"href",
			"https://github.com/xiaojiou176-open/sourceharbor/blob/main/docs/public-skills.md",
		);
		expect(
			screen.getByRole("link", { name: "Open media kit" }),
		).toHaveAttribute(
			"href",
			"https://github.com/xiaojiou176-open/sourceharbor/blob/main/docs/media-kit.md",
		);
		expect(
			screen.getByRole("link", { name: "Open Codex boundary" }),
		).toHaveAttribute(
			"href",
			"https://github.com/xiaojiou176-open/sourceharbor/blob/main/docs/compat/codex.md",
		);
		expect(
			screen.getByRole("link", { name: "Open Claude boundary" }),
		).toHaveAttribute(
			"href",
			"https://github.com/xiaojiou176-open/sourceharbor/blob/main/docs/compat/claude-code.md",
		);
		expect(
			screen.getByRole("link", { name: "Open OpenClaw boundary" }),
		).toHaveAttribute(
			"href",
			"https://github.com/xiaojiou176-open/sourceharbor/blob/main/docs/compat/openclaw.md",
		);
		expect(
			screen.getByRole("link", { name: "Open MCP registry pack" }),
		).toHaveAttribute(
			"href",
			"https://github.com/xiaojiou176-open/sourceharbor/blob/main/starter-packs/mcp-registry/README.md",
		);
	});
});
