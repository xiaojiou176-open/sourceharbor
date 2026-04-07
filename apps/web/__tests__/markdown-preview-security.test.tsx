import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MarkdownPreview } from "@/components/markdown-preview";

describe("MarkdownPreview security", () => {
	it("renders safe external links with noopener/noreferrer", () => {
		render(<MarkdownPreview markdown="[open](https://example.com/docs)" />);
		const link = screen.getByRole("link", { name: "open" });
		expect(link).toHaveAttribute("href", "https://example.com/docs");
		expect(link).toHaveAttribute("target", "_blank");
		expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
		expect(link).toHaveAttribute("rel", expect.stringContaining("noreferrer"));
	});

	it("blocks javascript/data scheme links", () => {
		render(
			<MarkdownPreview
				markdown={"[bad](javascript:alert(1))\n\n[data](data:text/html,hello)"}
			/>,
		);
		expect(screen.queryByRole("link", { name: "bad" })).not.toBeInTheDocument();
		expect(
			screen.queryByRole("link", { name: "data" }),
		).not.toBeInTheDocument();
		expect(screen.getByText("bad")).toBeInTheDocument();
		expect(screen.getByText("data")).toBeInTheDocument();
	});
});
