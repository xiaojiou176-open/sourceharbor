import type { Metadata } from "next";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { getLocaleMessages } from "@/lib/i18n/messages";
import { buildProductMetadata } from "@/lib/seo";

const proofCopy = getLocaleMessages().proofPage;

export const metadata: Metadata = buildProductMetadata({
	title: proofCopy.metadataTitle,
	description: proofCopy.metadataDescription,
	route: "proof",
});

export default function ProofPage() {
	const copy = getLocaleMessages().proofPage;
	const proofLayers = [
		{
			title: copy.layers.productSurfaceTitle,
			body: copy.layers.productSurfaceBody,
		},
		{
			title: copy.layers.localSupervisorTitle,
			body: copy.layers.localSupervisorBody,
		},
		{
			title: copy.layers.longSmokeTitle,
			body: copy.layers.longSmokeBody,
		},
		{
			title: copy.layers.remoteProofTitle,
			body: copy.layers.remoteProofBody,
		},
	];
	return (
		<div className="folo-page-shell folo-unified-shell">
			<div className="folo-page-header">
				<p className="folo-page-kicker">{copy.kicker}</p>
				<h1 className="folo-page-title" data-route-heading tabIndex={-1}>
					{copy.heroTitle}
				</h1>
				<p className="folo-page-subtitle">{copy.heroSubtitle}</p>
			</div>

			<section className="grid gap-4 lg:grid-cols-2">
				{proofLayers.map((item) => (
					<Card key={item.title} className="folo-surface border-border/70">
						<CardHeader>
							<CardTitle>{item.title}</CardTitle>
						</CardHeader>
						<CardContent className="text-sm text-muted-foreground">
							{item.body}
						</CardContent>
					</Card>
				))}
			</section>

			<Card className="folo-surface border-border/70">
				<CardHeader>
					<CardTitle>{copy.nextTruthfulJumpsTitle}</CardTitle>
					<CardDescription>{copy.nextTruthfulJumpsDescription}</CardDescription>
				</CardHeader>
				<CardContent className="flex flex-wrap gap-3">
					<Button asChild variant="outline" size="sm">
						<Link href="/">{copy.openCommandCenterButton}</Link>
					</Button>
					<Button asChild variant="outline" size="sm">
						<Link href="/ops">{copy.openOpsButton}</Link>
					</Button>
					<Button asChild variant="outline" size="sm">
						<Link href="/mcp">{copy.openMcpButton}</Link>
					</Button>
				</CardContent>
			</Card>
		</div>
	);
}
