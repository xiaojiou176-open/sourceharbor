import Image from "next/image";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import {
	editorialMono,
	editorialSans,
	editorialSerif,
} from "@/lib/editorial-fonts";
import type { SourceIdentityModel } from "@/lib/source-identity";
import { cn } from "@/lib/utils";

type SourceIdentityCardProps = {
	identity: SourceIdentityModel;
	className?: string;
	compact?: boolean;
	action?: ReactNode;
};

function relationBadgeTone(kind: string) {
	if (kind === "matched_subscription" || kind === "subscription_tracked") {
		return "border-emerald-500/45 bg-emerald-500/12 text-emerald-800";
	}
	if (kind === "new_source_universe" || kind === "subscription_candidate") {
		return "border-sky-500/45 bg-sky-500/12 text-sky-800";
	}
	if (kind === "manual_one_off" || kind === "manual_injected") {
		return "border-amber-500/45 bg-amber-500/12 text-amber-800";
	}
	return "border-border/60 bg-muted/15 text-foreground";
}

export function SourceIdentityCard({
	identity,
	className,
	compact = false,
	action,
}: SourceIdentityCardProps) {
	const visibleMeta = compact ? identity.meta.slice(0, 2) : identity.meta;
	return (
		<article
			className={cn(
				"rounded-[1.35rem] border border-border/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.98)_0%,rgba(248,249,255,0.9)_100%)] shadow-[0_18px_48px_-44px_rgba(15,23,42,0.36)]",
				compact ? "p-3.5" : "p-4",
				editorialSans.className,
				className,
			)}
		>
			<div
				className={cn(
					"grid gap-3",
					compact
						? "grid-cols-[76px_minmax(0,1fr)]"
						: "grid-cols-[112px_minmax(0,1fr)]",
				)}
			>
				<div className="space-y-2">
					<div className="relative overflow-hidden rounded-[1rem] border border-border/70 bg-muted/10">
						{identity.thumbnailUrl ? (
							<Image
								src={identity.thumbnailUrl}
								alt={`${identity.title} thumbnail`}
								width={640}
								height={compact ? 640 : 480}
								unoptimized={
									identity.thumbnailUrl.startsWith("data:image/")
										? true
										: undefined
								}
								className={cn(
									"h-full w-full object-cover",
									compact ? "aspect-square" : "aspect-[4/3]",
								)}
							/>
						) : (
							<div
								className={cn(
									"flex h-full w-full items-center justify-center bg-[linear-gradient(180deg,rgba(79,70,229,0.06)_0%,rgba(244,114,182,0.06)_100%)] text-[10px] font-semibold uppercase tracking-[0.28em] text-muted-foreground",
									compact ? "aspect-square" : "aspect-[4/3]",
								)}
							>
								{identity.avatarLabel}
							</div>
						)}
						<div className="absolute inset-x-0 bottom-0 h-14 bg-gradient-to-t from-black/28 via-black/6 to-transparent" />
						<div className="absolute bottom-2 left-2">
							{identity.avatarUrl ? (
								<Image
									src={identity.avatarUrl}
									alt={`${identity.title} avatar`}
									width={compact ? 30 : 36}
									height={compact ? 30 : 36}
									unoptimized={
										identity.avatarUrl.startsWith("data:image/")
											? true
											: undefined
									}
									className={cn(
										"rounded-full border border-white/80 bg-white/90 object-cover shadow-[0_8px_22px_-18px_rgba(15,23,42,0.4)]",
										compact ? "h-[1.875rem] w-[1.875rem]" : "h-9 w-9",
									)}
								/>
							) : (
								<div
									className={cn(
										"flex items-center justify-center rounded-full border border-white/80 bg-white/92 text-[10px] font-semibold text-slate-900 shadow-[0_8px_22px_-18px_rgba(15,23,42,0.4)]",
										compact ? "h-[1.875rem] w-[1.875rem]" : "h-9 w-9",
									)}
								>
									{identity.avatarLabel}
								</div>
							)}
						</div>
					</div>
					<p
						className={cn(
							"truncate text-[10px] uppercase tracking-[0.18em] text-muted-foreground",
							editorialMono.className,
						)}
					>
						{identity.avatarLabel}
					</p>
				</div>
				<div className="min-w-0 space-y-3">
					<div className="flex flex-wrap items-center gap-2">
						<Badge
							variant="outline"
							className={relationBadgeTone(identity.relationKind)}
						>
							{identity.relationLabel}
						</Badge>
					</div>
					<div className="space-y-1.5">
						{identity.eyebrow ? (
							<p
								className={cn(
									"text-[10px] uppercase tracking-[0.18em] text-muted-foreground",
									editorialMono.className,
								)}
							>
								{identity.eyebrow}
							</p>
						) : null}
						<p
							className={cn(
								"line-clamp-2 text-foreground",
								compact
									? "text-[0.98rem] leading-6"
									: "text-[1.08rem] leading-7",
								editorialSerif.className,
							)}
						>
							{identity.title}
						</p>
						<p
							className={cn(
								"line-clamp-2 text-muted-foreground",
								compact ? "text-[11px] leading-5" : "text-sm leading-6",
							)}
						>
							{identity.subtitle}
						</p>
					</div>
					{identity.description ? (
						<p
							className={cn(
								"line-clamp-2 text-muted-foreground",
								compact ? "text-[11px] leading-5" : "text-sm leading-6",
							)}
						>
							{identity.description}
						</p>
					) : null}
					<div className="flex flex-wrap gap-1.5">
						{visibleMeta.map((item) => (
							<Badge
								key={item}
								variant="outline"
								className={cn(
									"border-border/55 bg-background/75 px-2 py-0.5 text-[10px] text-muted-foreground",
									editorialMono.className,
								)}
							>
								{item}
							</Badge>
						))}
					</div>
					{action ? (
						<div className="border-t border-border/50 pt-2 text-sm">
							{action}
						</div>
					) : null}
				</div>
			</div>
		</article>
	);
}
