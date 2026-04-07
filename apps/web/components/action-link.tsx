"use client";

import Link from "next/link";
import type { ComponentProps } from "react";

import { Button } from "@/components/ui/button";

type ActionLinkProps = {
	href: string;
	children: React.ReactNode;
	variant?: ComponentProps<typeof Button>["variant"];
	size?: ComponentProps<typeof Button>["size"];
	className?: string;
	"aria-label"?: string;
	"data-interaction"?: string;
};

export function ActionLink({
	href,
	children,
	variant = "ghost",
	size = "sm",
	className,
	...props
}: ActionLinkProps) {
	return (
		<Button
			asChild
			variant={variant}
			size={size}
			className={className}
			{...props}
		>
			<Link href={href}>{children}</Link>
		</Button>
	);
}
