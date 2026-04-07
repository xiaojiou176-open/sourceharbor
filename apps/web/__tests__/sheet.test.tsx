import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
	Sheet,
	SheetContent,
	SheetDescription,
	SheetTitle,
	SheetTrigger,
} from "@/components/ui/sheet";

describe("Sheet", () => {
	it("uses localized close label and can hide the close button", () => {
		const { rerender } = render(
			<Sheet>
				<SheetTrigger>Open</SheetTrigger>
				<SheetContent side="right">
					<SheetTitle>Title</SheetTitle>
					<SheetDescription>Sheet description</SheetDescription>
					<div>Content</div>
				</SheetContent>
			</Sheet>,
		);

		fireEvent.click(screen.getByRole("button", { name: "Open" }));
		expect(screen.getByText("Close")).toHaveClass("sr-only");

		rerender(
			<Sheet defaultOpen>
				<SheetContent side="left" showCloseButton={false}>
					<SheetTitle>Title</SheetTitle>
					<SheetDescription>Sheet description</SheetDescription>
					<div>Content</div>
				</SheetContent>
			</Sheet>,
		);

		expect(screen.queryByText("Close")).not.toBeInTheDocument();
	}, 15_000);

	it("renders top and bottom sheet variants", () => {
		const { rerender } = render(
			<Sheet defaultOpen>
				<SheetContent side="top">
					<SheetTitle>Top sheet</SheetTitle>
					<SheetDescription>Top description</SheetDescription>
				</SheetContent>
			</Sheet>,
		);

		expect(
			screen.getByText("Top sheet").closest('[data-slot="sheet-content"]'),
		).toHaveClass("inset-x-0");

		rerender(
			<Sheet defaultOpen>
				<SheetContent side="bottom">
					<SheetTitle>Bottom sheet</SheetTitle>
					<SheetDescription>Bottom description</SheetDescription>
				</SheetContent>
			</Sheet>,
		);

		expect(
			screen.getByText("Bottom sheet").closest('[data-slot="sheet-content"]'),
		).toHaveClass("bottom-0");
	});
});
