"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
} from "@/components/ui/card";

type TrackedCreator = {
	name: string;
	uid: string;
	url: string;
};

type BilibiliDiscoveryDeskProps = {
	trackedCreators: TrackedCreator[];
};

function normalizeUid(value: string): string {
	return value.trim().replace(/\D+/g, "");
}

export function BilibiliDiscoveryDesk({
	trackedCreators,
}: BilibiliDiscoveryDeskProps) {
	const [searchQuery, setSearchQuery] = useState("");
	const [creatorUid, setCreatorUid] = useState(trackedCreators[0]?.uid ?? "");

	const searchHref = useMemo(() => {
		const query = searchQuery.trim();
		if (!query) return "https://search.bilibili.com/all";
		return `https://search.bilibili.com/all?keyword=${encodeURIComponent(query)}`;
	}, [searchQuery]);

	const creatorHref = useMemo(() => {
		const uid = normalizeUid(creatorUid);
		if (uid) return `https://space.bilibili.com/${uid}`;
		return trackedCreators[0]?.url ?? "https://space.bilibili.com/";
	}, [creatorUid, trackedCreators]);

	return (
		<Card className="folo-surface rounded-[1.6rem] border border-border/70 bg-background/95 shadow-sm">
			<CardHeader className="gap-2">
				<h2 className="text-xl font-semibold text-foreground">
					Bilibili discovery desk
				</h2>
				<CardDescription>
					Use discovery on purpose, then bring the creator space URL, UID, or
					single video URL back into SourceHarbor only after it earns a slot in
					the reading loop.
				</CardDescription>
			</CardHeader>
			<CardContent className="space-y-5">
				<div className="grid gap-3 md:grid-cols-3">
					<Button asChild variant="outline" size="sm">
						<Link href="https://www.bilibili.com/v/popular/all" target="_blank">
							Open hot now
						</Link>
					</Button>
					<Button asChild variant="outline" size="sm">
						<Link
							href="https://www.bilibili.com/v/popular/rank/all"
							target="_blank"
						>
							Open rank now
						</Link>
					</Button>
					<Button asChild variant="outline" size="sm">
						<Link href="https://www.bilibili.com/" target="_blank">
							Open home feed
						</Link>
					</Button>
				</div>

				<div className="grid gap-4 lg:grid-cols-2">
					<form
						action={searchHref}
						method="get"
						target="_blank"
						className="rounded-xl border border-border/60 bg-muted/15 p-4"
					>
						<label
							htmlFor="bilibili-discovery-search"
							className="text-sm font-medium text-foreground"
						>
							Search Bilibili
						</label>
						<input
							id="bilibili-discovery-search"
							aria-label="Search Bilibili"
							name="keyword"
							value={searchQuery}
							onChange={(event) => setSearchQuery(event.target.value)}
							placeholder="AI agent"
							className="mt-3 h-9 w-full rounded-md border border-border/60 bg-background px-3 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
						/>
						<p className="mt-3 text-sm text-muted-foreground">
							Search outside first when you want fresh creators, hot topics, or
							one-off videos. Paste the result back here only after it earns a
							persistent source or a one-off reading slot.
						</p>
						<Button type="submit" size="sm" className="mt-4">
							Search on Bilibili
						</Button>
					</form>

					<div className="rounded-xl border border-border/60 bg-muted/15 p-4">
						<label
							htmlFor="bilibili-discovery-creator"
							className="text-sm font-medium text-foreground"
						>
							Creator UID
						</label>
						<input
							id="bilibili-discovery-creator"
							aria-label="Creator UID"
							value={creatorUid}
							onChange={(event) => setCreatorUid(event.target.value)}
							placeholder="12345"
							className="mt-3 h-9 w-full rounded-md border border-border/60 bg-background px-3 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
						/>
						<p className="mt-3 text-sm text-muted-foreground">
							Use creator space when you want a durable recurring source. Use a
							video URL when it only deserves today&apos;s reading lane.
						</p>
						<Button asChild size="sm" className="mt-4">
							<Link href={creatorHref} target="_blank">
								Open creator space
							</Link>
						</Button>
					</div>
				</div>

				<div className="rounded-xl border border-border/60 bg-muted/15 p-4">
					<p className="text-sm font-medium text-foreground">
						Tracked creator shortcuts
					</p>
					{trackedCreators.length > 0 ? (
						<div className="mt-3 flex flex-wrap gap-2">
							{trackedCreators.slice(0, 4).map((creator) => (
								<Button
									asChild
									key={`${creator.uid}-${creator.name}`}
									variant="outline"
									size="sm"
								>
									<Link href={creator.url} target="_blank">
										{`Open tracked creator: ${creator.name}`}
									</Link>
								</Button>
							))}
						</div>
					) : (
						<p className="mt-3 text-sm text-muted-foreground">
							Once you save a Bilibili creator here, their space will show up as
							a reusable discovery shortcut.
						</p>
					)}
				</div>
			</CardContent>
		</Card>
	);
}
