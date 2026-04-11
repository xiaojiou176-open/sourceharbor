import Image from "next/image";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
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
		return "border-emerald-500/40 bg-emerald-500/10 text-emerald-700";
	}
	if (kind === "new_source_universe" || kind === "subscription_candidate") {
		return "border-sky-500/40 bg-sky-500/10 text-sky-700";
	}
	if (kind === "manual_one_off" || kind === "manual_injected") {
		return "border-amber-500/40 bg-amber-500/10 text-amber-700";
	}
	return "border-border/60 bg-muted/15 text-foreground";
}

export function SourceIdentityCard({
	identity,
	className,
	compact = false,
	action,
}: SourceIdentityCardProps) {
	return (
		<article
			className={cn(
				"rounded-[1.4rem] border border-border/70 bg-background/95 shadow-sm",
				compact ? "p-3" : "p-4",
				className,
			)}
		>
			<div
				className={cn(
					"grid gap-3",
					compact
						? "grid-cols-[84px_minmax(0,1fr)]"
						: "grid-cols-[120px_minmax(0,1fr)]",
				)}
			>
				<div className="relative overflow-hidden rounded-[1.1rem] border border-border/60 bg-muted/15">
					{identity.thumbnailUrl ? (
						<Image
							src={identity.thumbnailUrl}
							alt={`${identity.title} thumbnail`}
							width={640}
							height={compact ? 640 : 480}
							unoptimized={identity.thumbnailUrl.startsWith("data:image/")}
							className={cn(
								"h-full w-full object-cover",
								compact ? "aspect-[1/1]" : "aspect-[4/3]",
							)}
						/>
					) : (
						<div
							className={cn(
								"flex h-full w-full items-center justify-center bg-muted text-xs font-semibold uppercase tracking-[0.28em] text-muted-foreground",
								compact ? "aspect-[1/1]" : "aspect-[4/3]",
							)}
						>
							{identity.avatarLabel}
						</div>
					)}
					<div className="absolute inset-0 bg-gradient-to-t from-black/65 via-black/10 to-transparent" />
					<div className="absolute bottom-2 left-2 flex items-center gap-2">
						{identity.avatarUrl ? (
							<Image
								src={identity.avatarUrl}
								alt={`${identity.title} avatar`}
								width={compact ? 36 : 44}
								height={compact ? 36 : 44}
								unoptimized={identity.avatarUrl.startsWith("data:image/")}
								className={cn(
									"rounded-full border border-white/70 object-cover shadow-sm",
									compact ? "h-9 w-9" : "h-11 w-11",
								)}
							/>
						) : (
							<div
								className={cn(
									"flex items-center justify-center rounded-full border border-white/70 bg-white/90 text-[11px] font-semibold text-slate-900 shadow-sm",
									compact ? "h-9 w-9" : "h-11 w-11",
								)}
							>
								{identity.avatarLabel}
							</div>
						)}
						<div className="rounded-full bg-black/55 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-white/85">
							{identity.avatarLabel}
						</div>
					</div>
				</div>
				<div className="min-w-0 space-y-2">
					<div className="flex flex-wrap items-center gap-2">
						<Badge
							variant="outline"
							className={relationBadgeTone(identity.relationKind)}
						>
							{identity.relationLabel}
						</Badge>
						{identity.eyebrow ? (
							<Badge
								variant="outline"
								className="border-border/60 bg-muted/20 text-muted-foreground"
							>
								{identity.eyebrow}
							</Badge>
						) : null}
					</div>
					<div className="space-y-1">
						<p
							className={cn(
								"line-clamp-2 font-semibold text-foreground",
								compact ? "text-sm" : "text-base",
							)}
						>
							{identity.title}
						</p>
						<p
							className={cn(
								"text-muted-foreground",
								compact ? "text-xs" : "text-sm",
							)}
						>
							{identity.subtitle}
						</p>
					</div>
					{identity.description ? (
						<p
							className={cn(
								"line-clamp-2 text-muted-foreground",
								compact ? "text-xs" : "text-sm leading-6",
							)}
						>
							{identity.description}
						</p>
					) : null}
					<div className="flex flex-wrap gap-2">
						{identity.meta.map((item) => (
							<Badge
								key={item}
								variant="outline"
								className="border-border/50 bg-background/60 text-[11px] text-muted-foreground"
							>
								{item}
							</Badge>
						))}
					</div>
					{action ? <div className="pt-1">{action}</div> : null}
				</div>
			</div>
		</article>
	);
}
