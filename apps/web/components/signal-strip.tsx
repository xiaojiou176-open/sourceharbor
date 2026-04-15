type SignalStripItem = {
	label: string;
	value: number;
	max?: number;
	valueLabel?: string;
	detail?: string;
	tone?: "primary" | "success" | "warning" | "muted";
};

type SignalStripProps = {
	title: string;
	description?: string;
	items: SignalStripItem[];
};

const TONE_CLASS: Record<NonNullable<SignalStripItem["tone"]>, string> = {
	primary: "bg-primary/80",
	success: "bg-emerald-500/80",
	warning: "bg-amber-500/80",
	muted: "bg-muted-foreground/60",
};

export function SignalStrip({
	title,
	description,
	items,
}: SignalStripProps) {
	return (
		<div className="rounded-2xl border border-border/60 bg-background/70 p-4">
			<div className="space-y-1">
				<p className="text-sm font-semibold text-foreground">{title}</p>
				{description ? (
					<p className="text-sm text-muted-foreground">{description}</p>
				) : null}
			</div>
			<div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
				{items.map((item) => {
					const max = Math.max(item.max ?? item.value, 1);
					const width = `${Math.max(8, Math.min(100, (item.value / max) * 100))}%`;
					const tone = TONE_CLASS[item.tone ?? "primary"];
					return (
						<div
							key={`${item.label}-${item.valueLabel ?? item.value}`}
							className="space-y-2 rounded-xl border border-border/50 bg-muted/20 p-3"
						>
							<div className="flex items-center justify-between gap-3">
								<p className="text-sm font-medium text-foreground">
									{item.label}
								</p>
								<p className="text-sm text-muted-foreground">
									{item.valueLabel ?? item.value}
								</p>
							</div>
							<div className="h-2 overflow-hidden rounded-full bg-muted/50">
								<div className={`h-full rounded-full ${tone}`} style={{ width }} />
							</div>
							{item.detail ? (
								<p className="text-xs leading-5 text-muted-foreground">
									{item.detail}
								</p>
							) : null}
						</div>
					);
				})}
			</div>
		</div>
	);
}
