"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiClient } from "@/lib/api/client";
import { resolveWriteSessionToken } from "@/lib/api/url";

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
				{REPAIR_OPTIONS.map((option) => (
					<div
						key={option.mode}
						className="rounded-2xl border border-border/60 bg-muted/15 p-3"
					>
						<div className="flex items-start justify-between gap-3">
							<div className="space-y-1">
								<p className="font-medium text-foreground">{option.title}</p>
								<p className="text-sm leading-6 text-muted-foreground">
									{option.description}
								</p>
							</div>
							<Button
								type="button"
								size="sm"
								variant={option.mode === "patch" ? "hero" : "outline"}
								disabled={isPending}
								onClick={() => runRepair(option.mode)}
							>
								{isPending ? "Working..." : "Run"}
							</Button>
						</div>
					</div>
				))}
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
