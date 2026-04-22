import React from "react";
import {
	AbsoluteFill,
	Easing,
	Img,
	interpolate,
	spring,
	staticFile,
	useCurrentFrame,
	useVideoConfig,
} from "remotion";

type SourceHarborFrontDoorProps = {
	title: string;
	subtitle: string;
};

const palette = {
	ink: "#122530",
	muted: "#5a6875",
	background: "#eef3f6",
	card: "#fffdf7",
	border: "rgba(18, 37, 48, 0.12)",
	primary: "#155e57",
	primaryDark: "#134e4a",
	accent: "#f7b955",
	wash: "#d9ece7",
	deep: "#103734",
};

const screenshotShadow = "0 28px 64px rgba(16, 37, 48, 0.16)";

const SceneShell: React.FC<{
	children: React.ReactNode;
	light?: boolean;
}> = ({ children, light = false }) => (
	<AbsoluteFill
		style={{
			background: light
				? "linear-gradient(180deg, #f5f7fb 0%, #eef3f6 100%)"
				: "radial-gradient(circle at top right, rgba(247,185,85,0.18), transparent 34%), linear-gradient(180deg, #103734 0%, #0f2f2c 100%)",
			color: light ? palette.ink : "#fffaf0",
			fontFamily:
				'"Iowan Old Style", "Palatino Linotype", "Book Antiqua", Georgia, serif',
		}}
	>
		{children}
	</AbsoluteFill>
);

const SectionLabel: React.FC<{ text: string; light?: boolean }> = ({
	text,
	light = false,
}) => (
	<div
		style={{
			fontSize: 18,
			fontWeight: 700,
			letterSpacing: "0.22em",
			textTransform: "uppercase",
			color: light ? palette.primary : "#bde3da",
			fontFamily:
				'"IBM Plex Mono", "SFMono-Regular", Consolas, "Liberation Mono", monospace',
		}}
	>
		{text}
	</div>
);

const ProofChip: React.FC<{ text: string }> = ({ text }) => (
	<div
		style={{
			display: "inline-flex",
			alignItems: "center",
			borderRadius: 999,
			padding: "10px 18px",
			background: "rgba(255,255,255,0.72)",
			border: `1px solid ${palette.border}`,
			fontFamily:
				'"IBM Plex Mono", "SFMono-Regular", Consolas, "Liberation Mono", monospace',
			fontSize: 16,
			color: palette.ink,
		}}
	>
		{text}
	</div>
);

const ScreenshotCard: React.FC<{
	src: string;
	frame: number;
	title: string;
	caption: string;
	align?: "left" | "right";
}> = ({ src, frame, title, caption, align = "right" }) => {
	const { fps } = useVideoConfig();
	const progress = spring({
		fps,
		frame,
		config: {
			damping: 18,
			stiffness: 90,
			mass: 0.8,
		},
	});
	const translateX = interpolate(
		progress,
		[0, 1],
		[align === "right" ? 56 : -56, 0],
	);
	const opacity = interpolate(progress, [0, 1], [0, 1]);
	return (
		<div
			style={{
				flex: 1,
				display: "flex",
				flexDirection: "column",
				gap: 18,
				opacity,
				transform: `translateX(${translateX}px)`,
			}}
		>
			<div
				style={{
					borderRadius: 34,
					padding: 18,
					background: "rgba(255, 253, 247, 0.96)",
					border: `1px solid ${palette.border}`,
					boxShadow: screenshotShadow,
				}}
			>
				<Img
					src={src}
					style={{
						width: "100%",
						height: 420,
						objectFit: "cover",
						borderRadius: 24,
						border: `1px solid ${palette.border}`,
					}}
				/>
			</div>
			<div style={{ display: "grid", gap: 8 }}>
				<div
					style={{
						fontSize: 34,
						lineHeight: 1.08,
						fontWeight: 600,
						color: palette.ink,
					}}
				>
					{title}
				</div>
				<div
					style={{
						fontFamily:
							'"Public Sans", Inter, "Helvetica Neue", Arial, sans-serif',
						fontSize: 22,
						lineHeight: 1.5,
						color: palette.muted,
					}}
				>
					{caption}
				</div>
			</div>
		</div>
	);
};

const HomeScene: React.FC<SourceHarborFrontDoorProps> = ({
	title,
	subtitle,
}) => {
	const frame = useCurrentFrame();
	const { fps } = useVideoConfig();
	const copyProgress = spring({
		fps,
		frame,
		config: { damping: 18, stiffness: 100, mass: 0.85 },
	});
	const copyOpacity = interpolate(copyProgress, [0, 1], [0, 1]);
	const copyY = interpolate(copyProgress, [0, 1], [26, 0]);
	return (
		<SceneShell>
			<div
				style={{
					display: "grid",
					gridTemplateColumns: "0.95fr 1.05fr",
					gap: 48,
					height: "100%",
					padding: "72px 72px 64px",
				}}
				>
					<div
						style={{
							display: "flex",
							flexDirection: "column",
							justifyContent: "center",
						gap: 24,
						opacity: copyOpacity,
						transform: `translateY(${copyY}px)`,
						}}
					>
					<SectionLabel text="Read the finished surface first" />
					<div
						style={{
							fontSize: 82,
							lineHeight: 0.96,
							fontWeight: 600,
							letterSpacing: "-0.04em",
						}}
					>
						{title}
					</div>
					<div
						style={{
							fontFamily:
								'"Public Sans", Inter, "Helvetica Neue", Arial, sans-serif',
							fontSize: 27,
							lineHeight: 1.45,
							color: "#d7e8e3",
							maxWidth: 520,
						}}
					>
						{subtitle}
					</div>
					<div style={{ display: "flex", flexWrap: "wrap", gap: 14 }}>
						<ProofChip text="Finished reader" />
						<ProofChip text="Proof nearby" />
						<ProofChip text="Builders later" />
					</div>
				</div>
				<div
					style={{
						display: "flex",
						alignItems: "center",
						justifyContent: "flex-end",
					}}
				>
					<div
						style={{
							opacity: copyOpacity,
							transform: `translateY(${interpolate(copyProgress, [0, 1], [34, 0])}px)`,
						}}
					>
						<Img
							src={staticFile("desktop-reader-clean.png")}
							style={{
								width: 620,
								height: 520,
								objectFit: "cover",
								objectPosition: "top center",
								borderRadius: 38,
								border: "1px solid rgba(255,255,255,0.16)",
								boxShadow: "0 36px 80px rgba(0,0,0,0.24)",
							}}
						/>
					</div>
				</div>
			</div>
		</SceneShell>
	);
};

const TimelineScene: React.FC = () => {
	const frame = useCurrentFrame();
	return (
		<SceneShell light>
			<div
				style={{
					display: "grid",
					gridTemplateColumns: "0.92fr 1.08fr",
					gap: 42,
					height: "100%",
					padding: "72px 72px 64px",
					alignItems: "center",
				}}
			>
				<div style={{ display: "grid", gap: 20 }}>
					<SectionLabel text="Timeline, not a control panel" light />
					<div
						style={{
							fontSize: 74,
							lineHeight: 0.97,
							fontWeight: 600,
							letterSpacing: "-0.04em",
							color: palette.ink,
						}}
					>
						Open one story.
						<br />
						Leave filters for later.
					</div>
					<div
						style={{
							fontFamily:
								'"Public Sans", Inter, "Helvetica Neue", Arial, sans-serif',
							fontSize: 25,
							lineHeight: 1.48,
							color: palette.muted,
							maxWidth: 480,
						}}
					>
						The first page should feel like a reading desk. Generic IDs give
						way to readable headlines. Proof stays one click away.
					</div>
				</div>
				<ScreenshotCard
					src={staticFile("desktop-feed-clean.png")}
					frame={frame}
					title="Readable headlines beat helper copy"
					caption="The timeline now previews the story itself, while the selected reading surface keeps proof and controls in the second layer."
				/>
			</div>
		</SceneShell>
	);
};

const PublicFaceScene: React.FC = () => {
	const frame = useCurrentFrame();
	return (
		<SceneShell light>
			<div
				style={{
					display: "grid",
					gridTemplateColumns: "1.02fr 0.98fr",
					gap: 42,
					height: "100%",
					padding: "72px 72px 64px",
					alignItems: "center",
				}}
			>
				<ScreenshotCard
					src={staticFile("sourceharbor-social-preview.png")}
					frame={frame}
					title="Public surfaces stay thin, credible, and proof-backed"
					caption="README, social preview, and builder off-ramps should feel like one doorway instead of six competing menus."
					align="left"
				/>
				<div style={{ display: "grid", gap: 18 }}>
					<SectionLabel text="Outward expression" light />
					<div
						style={{
							fontSize: 68,
							lineHeight: 0.98,
							fontWeight: 600,
							letterSpacing: "-0.04em",
							color: palette.ink,
						}}
					>
						Make the first impression
						<br />
						feel finished.
					</div>
					<div
						style={{
							fontFamily:
								'"Public Sans", Inter, "Helvetica Neue", Arial, sans-serif',
							fontSize: 24,
							lineHeight: 1.5,
							color: palette.muted,
							maxWidth: 440,
						}}
					>
						SourceHarbor should read like a product: see the story, inspect the
						proof, then open builders only when you truly need them.
					</div>
					<div
						style={{
							display: "grid",
							gap: 12,
							marginTop: 8,
						}}
					>
						{[
							"See it fast",
							"Run one real local flow",
							"Keep builders as the deliberate second door",
						].map((item) => (
							<div
								key={item}
								style={{
									display: "flex",
									alignItems: "center",
									gap: 12,
									fontFamily:
										'"Public Sans", Inter, "Helvetica Neue", Arial, sans-serif',
									fontSize: 20,
									color: palette.ink,
								}}
							>
								<div
									style={{
										width: 10,
										height: 10,
										borderRadius: 999,
										background: palette.primary,
									}}
								/>
								{item}
							</div>
						))}
					</div>
				</div>
			</div>
		</SceneShell>
	);
};

const EndCard: React.FC = () => {
	const frame = useCurrentFrame();
	const { fps } = useVideoConfig();
	const progress = spring({
		fps,
		frame,
		config: { damping: 16, stiffness: 110, mass: 0.9 },
	});
	return (
		<SceneShell>
			<div
				style={{
					display: "flex",
					height: "100%",
					alignItems: "center",
					justifyContent: "center",
					padding: 72,
				}}
			>
				<div
					style={{
						width: 980,
						borderRadius: 38,
						padding: "54px 56px",
						background: "rgba(255, 253, 247, 0.96)",
						border: `1px solid ${palette.border}`,
						boxShadow: screenshotShadow,
						opacity: interpolate(progress, [0, 1], [0, 1]),
						transform: `translateY(${interpolate(progress, [0, 1], [26, 0])}px)`,
					}}
				>
					<SectionLabel text="SourceHarbor" light />
					<div
						style={{
							fontSize: 76,
							lineHeight: 0.97,
							fontWeight: 600,
							letterSpacing: "-0.04em",
							color: palette.ink,
							marginTop: 18,
						}}
					>
						Read first.
						<br />
						Inspect proof second.
					</div>
					<div
						style={{
							display: "flex",
							alignItems: "center",
							gap: 16,
							marginTop: 28,
							fontFamily:
								'"Public Sans", Inter, "Helvetica Neue", Arial, sans-serif',
							fontSize: 25,
							lineHeight: 1.5,
							color: palette.muted,
						}}
					>
						<div
							style={{
								padding: "16px 24px",
								borderRadius: 999,
								background: `linear-gradient(135deg, ${palette.primary} 0%, ${palette.primaryDark} 100%)`,
								color: "#fff",
								fontWeight: 600,
							}}
						>
							/reader
						</div>
						<div>Then open Search, Ask, and Builders only when the reading path asks for them.</div>
					</div>
				</div>
			</div>
		</SceneShell>
	);
};

export const SourceHarborFrontDoor: React.FC<SourceHarborFrontDoorProps> = ({
	title,
	subtitle,
}) => {
	const frame = useCurrentFrame();
	const scene = Math.floor(frame / 120);
	const overlayOpacity = interpolate(frame, [0, 456, 479], [1, 1, 0], {
		easing: Easing.bezier(0.2, 0, 0, 1),
		extrapolateLeft: "clamp",
		extrapolateRight: "clamp",
	});

	return (
		<AbsoluteFill style={{ opacity: overlayOpacity }}>
			{scene === 0 ? <HomeScene title={title} subtitle={subtitle} /> : null}
			{scene === 1 ? <TimelineScene /> : null}
			{scene === 2 ? <PublicFaceScene /> : null}
			{scene >= 3 ? <EndCard /> : null}
		</AbsoluteFill>
	);
};
