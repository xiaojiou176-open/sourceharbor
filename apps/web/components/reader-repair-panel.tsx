"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiClient } from "@/lib/api/client";
import { resolveWriteSessionToken } from "@/lib/api/url";
import { editorialMono } from "@/lib/editorial-fonts";

type ReaderRepairPanelProps = {
	documentId: string;
	publishedWithGap: boolean;
	repairHistoryCount: number;
	sectionIds: string[];
	sessionToken?: string;
};

type RepairMode = "patch" | "section" | "cluster";

const REPAIR_OPTIONS: Array<{
	mode: RepairMode;
	title: string;
	description: string;
}> = [
	{
		mode: "patch",
		title: "Patch repair",
		description:
			"Try the smallest safe repair first and keep the reading unit intact.",
	},
	{
		mode: "section",
		title: "Section refresh",
		description:
			"Rebuild the current section set when the gap is local, not structural.",
	},
	{
		mode: "cluster",
		title: "Cluster rebuild",
		description:
			"Use the full rebuild only when the document-level evidence pack needs a larger reset.",
	},
];

export function ReaderRepairPanel({
	documentId,
	publishedWithGap,
	repairHistoryCount,
	sectionIds,
	sessionToken,
}: ReaderRepairPanelProps) {
	const router = useRouter();
	const [statusMessage, setStatusMessage] = useState<string | null>(null);
	const [errorMessage, setErrorMessage] = useState<string | null>(null);
	const [isPending, startTransition] = useTransition();
	const effectiveSessionToken = resolveWriteSessionToken(sessionToken);

	function runRepair(mode: RepairMode) {
		setStatusMessage(null);
		setErrorMessage(null);
		startTransition(async () => {
			try {
				const repaired = await apiClient.repairPublishedReaderDocument(
					documentId,
					{
						repair_mode: mode,
						section_ids: mode === "section" ? sectionIds : undefined,
					},
					effectiveSessionToken
						? { webSessionToken: effectiveSessionToken }
						: undefined,
				);
				setStatusMessage(
					`Created version ${repaired.version} via ${repaired.materialization_mode}. Opening the repaired edition now.`,
				);
				router.push(`/reader/${repaired.id}`);
				router.refresh();
			} catch (error) {
				setErrorMessage(
					error instanceof Error
						? error.message
						: "Repair could not be completed right now.",
				);
			}
		});
	}

	return (
		<Card className="border-border/70 bg-background/95 shadow-sm">
			<CardHeader className="space-y-3 pb-4">
				<div className="flex flex-wrap items-center gap-2">
					<Badge variant={publishedWithGap ? "secondary" : "outline"}>
						{publishedWithGap ? "Repair recommended" : "Repair optional"}
					</Badge>
					<Badge variant="outline">{repairHistoryCount} prior repairs</Badge>
				</div>
				<CardTitle className="text-base">Repair this reading unit</CardTitle>
				<p className="text-sm leading-6 text-muted-foreground">
					Repair belongs beside the warning and coverage rails, not in a hidden
					operator console. Start small, then escalate only when the gap is
					structural.
				</p>
			</CardHeader>
			<CardContent className="space-y-3">
				<div className="rounded-[1.35rem] border border-border/60 bg-muted/12">
					{REPAIR_OPTIONS.map((option, index) => (
						<div
							key={option.mode}
							className={`grid gap-3 px-4 py-4 md:grid-cols-[92px_minmax(0,1fr)_auto] md:items-start ${
								index > 0 ? "border-t border-border/60" : ""
							}`}
						>
							<p
								className={`text-[11px] uppercase tracking-[0.22em] text-muted-foreground ${editorialMono.className}`}
							>
								{String(index + 1).padStart(2, "0")} {option.mode}
							</p>
							<div className="space-y-1">
								<p className="font-medium text-foreground">{option.title}</p>
								<p className="text-sm leading-6 text-muted-foreground">
									{option.description}
								</p>
							</div>
							<Button
								type="button"
								size="sm"
								variant={option.mode === "patch" ? "hero" : "surface"}
								disabled={isPending}
								onClick={() => runRepair(option.mode)}
							>
								{isPending ? "Working..." : "Run"}
							</Button>
						</div>
					))}
				</div>
				{statusMessage ? (
					<p className="text-sm text-emerald-700">{statusMessage}</p>
				) : null}
				{errorMessage ? (
					<p role="alert" className="text-sm text-destructive">
						{errorMessage}
					</p>
				) : null}
			</CardContent>
		</Card>
	);
}
