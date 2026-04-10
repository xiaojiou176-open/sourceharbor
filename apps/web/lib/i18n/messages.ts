export const SUPPORTED_LOCALES = ["en", "zh-CN"] as const;

export type SupportedLocale = (typeof SUPPORTED_LOCALES)[number];

export const DEFAULT_LOCALE: SupportedLocale = "en";

const MESSAGES = {
	en: {
		common: {
			close: "Close",
		},
		routeTransition: {
			announcementPrefix: "Switched to:",
			labels: {
				home: "Home",
				subscriptions: "Subscriptions",
				search: "Search",
				ask: "Ask",
				mcp: "MCP Quickstart",
				ops: "Ops inbox",
				reader: "Reader",
				watchlists: "Watchlists",
				trends: "Trends",
				briefings: "Briefings",
				playground: "Playground",
				proof: "Proof",
				knowledge: "Knowledge",
				jobs: "Jobs",
				ingestRuns: "Ingest runs",
				feed: "Digest feed",
				settings: "Settings",
				useCases: "Use cases",
				page: "Page",
			},
		},
		formValidation: {
			required: "Fill in and fix the required fields before submitting.",
			requireOne: "Fill in at least one required source before submitting.",
			requireOneExclusive:
				"Only one source can be filled right now. Clear the extra inputs before submitting.",
		},
		loading: {
			app: {
				title: "Dashboard loading",
				message: "Loading the command center. Please wait.",
			},
			feed: {
				title: "Digest feed loading",
				message: "Loading the digest feed. Please wait.",
			},
			jobs: {
				title: "Job trace loading",
				message: "Loading job details. Please wait.",
			},
			settings: {
				title: "Settings loading",
				message: "Loading notification settings. Please wait.",
			},
			subscriptions: {
				title: "Loading subscriptions",
				message: "Loading subscription data. Please wait.",
			},
		},
		submitButton: {
			defaultPendingLabel: "Submitting…",
			pendingBadge: "Working",
			pendingSrOnly: "Submitting. Please wait.",
		},
		syncNow: {
			idle: {
				buttonLabel: "Sync now",
				badgeLabel: "Idle",
				statusLabel: "Idle: sync the newest source updates on demand.",
			},
			loading: {
				buttonLabel: "Syncing…",
				badgeLabel: "Syncing",
				statusLabel: "Fetching and analyzing new content. Please wait.",
				liveStatusLabel: "Sync in progress. Please wait.",
				retryTitle: "Sync failed. Press Enter or Space to retry.",
			},
			done: {
				buttonLabel: "Sync complete",
				badgeLabel: "Done",
				statusLabel: "Sync complete. Refreshing the list next.",
				liveStatusLabel: "Sync complete. Refreshing the list now.",
			},
			error: {
				buttonLabel: "Sync failed, retry",
				badgeLabel: "Retry needed",
				statusLabel:
					"Sync failed. Check the network or API health, then retry.",
				liveStatusLabel:
					"Sync failed. Check the network or API health, then retry.",
				retryTitle: "Sync failed. Press Enter or Space to retry.",
			},
		},
		relativeTime: {
			soon: "soon",
			tomorrow: "tomorrow",
			justNow: "just now",
			minuteFuture: "in {count} minute | in {count} minutes",
			hourFuture: "in {count} hour | in {count} hours",
			dayFuture: "in {count} day | in {count} days",
			weekFuture: "in {count} week | in {count} weeks",
			monthFuture: "in {count} month | in {count} months",
			yearFuture: "in {count} year | in {count} years",
			minutePast: "{count} minute ago | {count} minutes ago",
			hourPast: "{count} hour ago | {count} hours ago",
			dayPast: "{count} day ago | {count} days ago",
			weekPast: "{count} week ago | {count} weeks ago",
			monthPast: "{count} month ago | {count} months ago",
			yearPast: "{count} year ago | {count} years ago",
			absoluteLocale: "en-US",
		},
		dashboard: {
			metadataTitle: "Command Center",
			metadataDescription:
				"SourceHarbor command center for AI knowledge intake, grounded retrieval, operator triage, and builder entry through MCP and HTTP API.",
			kicker: "SourceHarbor Command Center",
			heroTitle: "AI knowledge control tower",
			heroSubtitle:
				"Run intake, grounded retrieval, job orchestration, and agent reuse from one operator-facing command center.",
			frontDoors: {
				subscriptionsTitle: "Source-universe intake",
				subscriptionsDescription:
					"Start from strong-supported YouTube and Bilibili templates, then widen to RSSHub routes and generic RSS without pretending every route is already proven.",
				subscriptionsCta: "Open Subscriptions",
				subscriptionsHint:
					"One shared template catalog now drives Web, API, and MCP intake.",
				searchTitle: "Search front door",
				searchDescription:
					"Search digests, knowledge cards, transcripts, and related evidence from one operator-facing route.",
				searchCta: "Open Search",
				knowledgeCta: "Open Knowledge",
				askTitle: "Ask your sources",
				askDescription:
					"Carry briefing-backed story context into answer, changes, and evidence instead of stopping at raw retrieval hits.",
				askCta: "Open Ask",
				briefingsCta: "Open Briefings",
				askHint:
					"Ask now reuses the server-owned story payload shared with Briefings instead of a second browser-side view model.",
				mcpTitle: "MCP front door",
				mcpDescription:
					"Reuse the same intake, story, job, and retrieval truth through MCP instead of rebuilding a second agent surface.",
				mcpCta: "Open MCP quickstart",
				jobCta: "Inspect job evidence",
			},
			sectionHeadings: {
				whyNow: "Why builders keep reading",
				firstHop: "Choose your first path",
				primaryFrontDoors: "Primary front doors",
				builderEntryPoints: "Builder entry points",
				compounderSurfaces: "Compounder surfaces",
				keyMetrics: "Command center metrics",
			},
			whyNow: {
				sharedTruthTitle: "One truth across Web, API, and MCP",
				sharedTruthDescription:
					"Operators and agent builders read the same jobs, artifacts, and retrieval state instead of three parallel product shells.",
				proofFirstTitle: "Proof sits next to the product story",
				proofFirstDescription:
					"README, proof, runtime truth, and job receipts stay on one line so newcomers can trust what they see before they commit to a full run.",
				returnLoopTitle: "Worth returning to after the first run",
				returnLoopDescription:
					"Watchlists, trends, briefings, bundles, and the playground make SourceHarbor a reusable control tower instead of a one-shot summarizer.",
			},
			firstHop: {
				evaluateTitle: "See whether the product is real",
				evaluateDescription:
					"Start with the fastest no-boot preview, then read the proof ladder before you commit to a full local run.",
				evaluatePrimaryCta: "Open no-boot tour",
				evaluateSecondaryCta: "Open proof ladder",
				operateTitle: "Run SourceHarbor as an operator",
				operateDescription:
					"Take the shortest truthful local path first, then move into subscriptions, search, and ops once the stack is up.",
				operatePrimaryCta: "Open start-here guide",
				operateSecondaryCta: "Start with Subscriptions",
				operateTertiaryCta: "Open Ops inbox",
				buildTitle: "Build with the same system truth",
				buildDescription:
					"Jump into MCP, builders docs, and distribution status when you are here to integrate rather than just evaluate the product surface.",
				buildPrimaryCta: "Open MCP quickstart",
				buildSecondaryCta: "Open builders guide",
				buildTertiaryCta: "Open distribution status",
			},
			compounders: {
				watchlistsTitle: "Watchlists are tracking objects",
				watchlistsDescription:
					"Save the watchlist here, then move into Trends for the unified information surface instead of treating both pages like the same thing.",
				watchlistsCta: "Open Watchlists",
				trendsTitle: "Trends are the compounder front door",
				trendsDescription:
					"Start here when you want the repeated story across runs: merged stories up top, recent evidence runs below, and the next jump into Briefings or Jobs.",
				trendsCta: "Open Trends",
				briefingsTitle: "Briefings are the shared story surface",
				briefingsDescription:
					"Briefings lower cognitive load: current story first, then the delta, then evidence drill-down, with Ask reusing the same selected-story truth.",
				briefingsCta: "Open Briefings",
				bundleTitle: "Evidence bundle",
				bundleDescription:
					"Carry a run forward as an internal bundle with digest, trace summary, knowledge cards, and artifact manifest instead of pasting screenshots into chat.",
				bundleCta: "Open Job Trace",
				bundleHint: "Download the bundle from any job detail page.",
				playgroundTitle: "Playground stays sample-proof",
				playgroundDescription:
					"Explore a clearly labeled sample-proof lane and then jump back to live front doors when you need current operator truth.",
				playgroundCta: "Open Playground",
				proofCta: "Open Proof",
				useCasesCta: "Open use case pages",
			},
			loadErrorTitle: "Unable to load the command center",
			retryCurrentPage: "Retry this page",
			metricsRegionLabel: "Key metrics",
			metrics: {
				subscriptions: {
					title: "Subscriptions",
					unavailable: "Subscription data is temporarily unavailable",
					emptyCta: "Add your first subscription →",
				},
				discoveredVideos: {
					title: "Discovered videos",
					unavailable: "Discovered video data is temporarily unavailable",
				},
				runningJobs: {
					title: "Running / queued",
					unavailable: "Running and queued job data is temporarily unavailable",
				},
				failedJobs: {
					title: "Failed jobs",
					unavailable: "Failed job data is temporarily unavailable",
					openFailed: "Open failed jobs →",
					openOps: "Open Ops inbox →",
				},
				unavailableOutput: "Data unavailable",
			},
			pollIngest: {
				title: "Poll subscriptions",
				description:
					"Create a new ingest run, then jump into jobs and traces instead of guessing whether intake actually moved.",
				platformLabel: "Platform (optional)",
				maxNewVideosLabel: "Maximum new videos",
				submit: "Run ingest poll",
				submitPending: "Queuing ingest…",
				submitStatus: "Creating a new ingest run. Please wait.",
				queueLink: "Open job queue →",
			},
			processVideo: {
				title: "Process a single source",
				description:
					"Queue one source URL into the pipeline and inspect the resulting trace, artifacts, and retrieval surface.",
				platformLabel: "Platform *",
				urlLabel: "Source URL *",
				modeLabel: "Mode *",
				forceLabel: "Force rerun",
				submit: "Start processing",
				submitPending: "Creating job…",
				submitStatus: "Creating a new processing job. Please wait.",
				jobDetailLink: "Open job detail →",
			},
			ingestRuns: {
				title: "Recent ingest runs",
				description:
					"Use this like a receiving ledger. If you just triggered intake, this section should confirm whether the run actually moved.",
				viewAll: "Open all ingest runs →",
				unavailable: "Ingest run data is temporarily unavailable.",
				empty: "No ingest runs yet.",
				caption: "Recent ingest run list",
				platform: "Platform",
				status: "Status",
				newJobs: "New jobs",
				candidates: "Candidates",
				allPlatforms: "All",
			},
			recentVideos: {
				title: "Recent videos",
				description:
					"Only the 10 newest videos are shown here. Jump to the job trace to inspect the full run history.",
				viewAll: "Open all jobs →",
				empty: "No videos yet.",
				unavailable: "Unable to load the video list right now.",
				caption: "Recent video list",
				titleColumn: "Title",
				platformColumn: "Platform",
				statusColumn: "Status",
				lastJobColumn: "Latest job",
			},
			pollPlatformOptions: {
				all: "All",
			},
			processModeOptions: {
				full: "Full run",
				textOnly: "Text only",
				refreshComments: "Refresh comments",
				refreshLlm: "Refresh LLM outputs",
			},
		},
		ops: {
			metadataTitle: "Ops Inbox",
			metadataDescription:
				"Operator inbox for SourceHarbor failures, provider health, delivery readiness, hardening gates, and recommended next steps.",
			kicker: "SourceHarbor Ops",
			heroTitle: "Ops inbox",
			heroSubtitle:
				"Open the operator queue for failures, provider health, delivery readiness, and the next action to take.",
			loadErrorTitle: "Unable to aggregate Ops diagnostics",
			loadErrorDescription:
				"Check API health and the local full-stack status, then retry this page.",
			partialDataTitle: "Some diagnostics are temporarily unavailable",
			partialDataDescription:
				"This page keeps the items that did load. Check API health and doctor before re-running the full Ops fetch.",
			backToDashboard: "Back to command center",
			summary: {
				attentionItems: {
					title: "Attention items",
					description: "Total queue items that currently need operator review.",
				},
				failedJobs: {
					title: "Failed jobs",
					description:
						"Jobs that should send you back to the job trace before anything else.",
				},
				failedIngest: {
					title: "Failed ingest runs",
					description:
						"Ingest batches that did not launch or failed part-way through.",
				},
				notificationGate: {
					title: "Notification / gate issues",
					description:
						"A combined count of notification readiness, provider health, and hardening gates.",
				},
			},
			inbox: {
				title: "Ops inbox",
				description:
					"Treat this like the operator mailbox. Each item gives you one primary jump target instead of making you guess the right ledger.",
				empty:
					"There are no operator issues to triage right now. Recent jobs, ingest runs, and notification paths are inside the acceptable range.",
			},
			nextSteps: {
				title: "Recommended next steps",
				description:
					"Treat this as the operator copilot layer. It translates gates and inbox items into the next few moves instead of making you parse every table by hand.",
				noActions:
					"There are no urgent next steps right now. Stay on this page only if you want to inspect provider health or delivery readiness in detail.",
				triagePrefix: "Triage inbox item",
				gatePrefix: "Review hardening gate",
				openAction: "Open action",
			},
			providerHealth: {
				title: "Provider health",
				description:
					"Use this as the fast answer to whether the whole system is drifting. Yellow means operator review; red means a recent explicit failure.",
				empty: "No provider health incidents are currently recorded.",
				defaultMessage: "Provider health needs operator review.",
			},
			notificationReadiness: {
				title: "Notification readiness",
				description:
					"Keep missing config separate from actual send failures so the team does not flatten both into “notifications are broken.”",
				empty: "There are no pending notification deliveries right now.",
			},
		},
		settings: {
			metadataTitle: "Settings",
			metadataDescription:
				"Notification delivery settings, daily digest scheduling, failure alerts, and test-send controls for SourceHarbor operators.",
			kicker: "SourceHarbor Settings",
			heroTitle: "Notification settings",
			heroSubtitle:
				"Control digest delivery, failure alerts, and test-send behavior from one operator surface.",
			loadErrorTitle: "Unable to load settings",
			retryCurrentPage: "Retry this page",
			configSectionTitle: "Notification configuration",
			configDates: "Created: {createdAt} | Updated: {updatedAt}",
			enabledLabel: "Enable notifications",
			toEmailLabel: "Recipient email",
			dailyDigestLabel: "Enable daily digest",
			dailyDigestHourLabel: "Daily digest send hour (UTC)",
			dailyDigestHint:
				"Local-time preview: this field uses a UTC hour. Convert your local target hour into UTC before saving.",
			failureAlertLabel: "Enable failure alerts",
			saveButton: "Save configuration",
			savePending: "Saving…",
			saveStatus: "Saving notification settings. Please wait.",
			testSectionTitle: "Send test notification",
			testRecipientDescription: "Current default recipient: {email}",
			testRecipientMissing:
				"Current default recipient: not set yet. Add one above before sending a test message.",
			overrideRecipientLabel: "Override recipient (optional)",
			overrideRecipientPlaceholder:
				"Leave blank to use the configured recipient",
			subjectLabel: "Subject (optional)",
			subjectPlaceholder: "SourceHarbor test notification",
			bodyLabel: "Body (optional)",
			bodyPlaceholder: "This is a SourceHarbor test notification.",
			sendButton: "Send test email",
			sendPending: "Sending…",
			sendStatus: "Sending the test notification. Please wait.",
		},
		mcpPage: {
			metadataTitle: "MCP",
			metadataDescription:
				"Agent-facing SourceHarbor MCP quickstart, with real startup commands, representative tools, and builder-ready MCP/API positioning.",
			kicker: "SourceHarbor MCP Front Door",
			heroTitle: "MCP Quickstart",
			heroSubtitle:
				"Treat this as the agent-facing control plane. Web serves operators, API serves system integrations, and MCP serves assistants and workflows, while all three point at the same pipeline.",
			startTitle: "Start locally in one command",
			startDescription:
				"MCP is not a second copy of the business logic. Use the thin repo-local CLI facade to discover the route first, then start the same API-backed system through MCP.",
			startNote:
				"`./bin/sourceharbor mcp` routes to the same FastMCP server wired in apps/mcp/server.py. `./bin/dev-mcp` remains the direct underlying entrypoint.",
			toolsTitle: "Representative tools",
			toolsDescription:
				"These are enough to explain the surface in under three minutes.",
			relationshipTitle: "How MCP relates to the rest of the product",
			relationshipDescription:
				"Web is the operator-facing command center. API is the shared contract. MCP is the agent-facing surface. SourceHarbor routes MCP through the API instead of letting tools talk straight to the database.",
			searchCta: "Open Search",
			askCta: "Open Ask",
		},
		knowledgePage: {
			metadataTitle: "Knowledge",
			metadataDescription:
				"SourceHarbor knowledge layer for extracted knowledge cards, job-linked evidence, and reusable long-lived assets.",
			kicker: "SourceHarbor Knowledge Layer",
			heroTitle: "Knowledge",
			heroSubtitle:
				"Treat this as the long-lived asset layer extracted from digests. It behaves more like a knowledge-card cabinet than a one-time reading flow.",
			filterTitle: "Filter knowledge cards",
			filterDescription:
				"Use job, video, card type, topic, and claim filters to narrow the cabinet before you inspect the cards.",
			filterLabels: {
				jobId: "Job ID",
				videoId: "Video ID",
				cardType: "Card type",
				topic: "Topic",
				claimKind: "Claim kind",
				limit: "Limit",
			},
			idPlaceholder: "11111111-1111-1111-1111-111111111111",
			filterButton: "Filter",
			clearButton: "Clear",
			totalCards: "Total cards",
			uniqueJobs: "Unique jobs",
			cardTypes: "Card types",
			sectionTitle: "Knowledge cards",
			sectionDescription:
				"This surface shows the latest extracted knowledge cards. Jump back into Job Trace when you need the full run context.",
			loadError: "Unable to load knowledge cards right now.",
			empty: "No knowledge cards yet.",
			jobTraceCta: "Job Trace",
			openJobTraceButton: "Open job trace",
			openJobTraceAriaPrefix: "Open job trace for",
			sameTypeButton: "Same type",
			metaLabels: {
				job: "Job",
				video: "Video",
				order: "Order",
				topic: "Topic",
			},
		},
		ingestRunsPage: {
			metadataTitle: "Ingest Runs",
			metadataDescription:
				"SourceHarbor intake ledger for recent ingest runs, candidate counts, job creation, and batch-level run detail.",
			kicker: "SourceHarbor Intake",
			heroTitle: "Ingest Runs",
			heroSubtitle:
				"Treat this as the intake ledger. It tells you whether each pull actually launched, how many candidates it found, and how many jobs it created.",
			filterTitle: "Find an ingest run",
			filterDescription:
				"Enter a run ID to inspect one intake batch. Leave it empty to review the most recent batches.",
			runIdLabel: "Run ID",
			runIdPlaceholder: "11111111-1111-1111-1111-111111111111",
			searchButton: "Search",
			loadErrorTitle: "Load failed",
			loadErrorDescription: "Unable to load ingest runs right now.",
			sectionTitle: "Recent ingest runs",
			sectionDescription:
				"The latest 10 intake batches, so you can quickly confirm whether source intake is still moving.",
			platform: "Platform",
			status: "Status",
			jobs: "Jobs",
			candidates: "Candidates",
			created: "Created",
			allPlatforms: "all",
			empty: "No ingest runs yet.",
			detailTitle: "Run detail",
			detailDescription:
				"Treat this section like the itemized receipt for one intake batch.",
			detailEmpty: "This run does not have item detail yet.",
			detailFields: {
				runId: "Run ID",
				workflow: "Workflow",
				jobsCreated: "Jobs created",
				candidates: "Candidates",
			},
			itemsTableCaption: "Ingest run items",
			itemsTableHeaders: {
				videoUid: "Video UID",
				title: "Title",
				job: "Job",
				type: "Type",
				status: "Status",
			},
		},
		feedPage: {
			metadataTitle: "Digest Feed",
			metadataDescription:
				"SourceHarbor digest feed for reading entries, filtering source/category/feedback, and moving from feed curation into reading pane, job trace, and evidence.",
			kicker: "SourceHarbor Feed",
			heroTitle: "Digest Feed",
			heroSubtitle:
				"Browse digest entries and body content in one reading flow, with quick source and category filtering when you need it.",
			filterRegionLabel: "Digest filters",
			filterLabels: {
				source: "Source",
				category: "Category",
				feedback: "Feedback",
				sort: "Sort",
			},
			filterButton: "Filter",
			clearButton: "Clear",
			retryCurrentPageButton: "Retry current page",
			emptyTitle: "No AI digest entries yet",
			emptyFiltered: "No results match the current filters. Try clearing them.",
			emptyUnfiltered:
				"There are no processed videos or articles yet. Add a subscription and trigger intake first.",
			goToSubscriptionsButton: "Go to subscriptions",
			paginationLabel: "Pagination",
			pagePrefix: "Page",
			previousPageButton: "← Previous page",
			nextPageButton: "Next page →",
			sourceOptions: {
				all: "All sources",
				youtube: "YouTube",
				bilibili: "Bilibili",
				rss: "RSS",
			},
			feedbackOptions: {
				all: "All feedback",
				saved: "Saved",
				useful: "Useful",
				noisy: "Noisy",
				dismissed: "Dismissed",
				archived: "Archived",
			},
			sortOptions: {
				recent: "Recent first",
				curated: "Curated first",
			},
			categoryOptions: {
				all: "All categories",
				tech: "Tech",
				creator: "Creator",
				macro: "Macro",
				ops: "Ops",
				misc: "Misc",
			},
			subscriptionFilterLabel: "Subscription",
		},
		subscriptionsPage: {
			metadataTitle: "Subscriptions",
			metadataDescription:
				"SourceHarbor source intake front door for strong YouTube and Bilibili presets, general RSSHub routes, and generic RSS feeds, with guided template setup and bulk subscription management.",
			kicker: "SourceHarbor Sources",
			heroTitle: "Subscriptions",
			heroSubtitle:
				"Start with strong YouTube and Bilibili presets, branch into RSSHub routes or generic feeds when the source universe widens, and keep the intake contract honest from the first click.",
			supportMatrixTitle: "Support levels at a glance",
			supportMatrixDescription:
				"Think of this like an intake menu. Some source shapes are already plated and tested, some are broadly useful, and some still need route-level proof before you trust them every day.",
			supportLevels: {
				strong: {
					title: "Strong support",
					description:
						"YouTube channels and Bilibili creators are the clearest, most guided subscription paths right now.",
				},
				general: {
					title: "General support",
					description:
						"RSSHub routes and generic RSS feeds widen the universe, but the quality still depends on the route or feed you bring in.",
				},
				proving: {
					title: "Needs proof",
					description:
						"Route-specific or unusual source patterns should be treated as real experiments until the feed stays stable in live runs.",
				},
			},
			templateSectionTitle: "Choose a source template",
			templateSectionDescription:
				"Templates pre-wire platform, source type, and adapter defaults so the form feels like guided intake instead of a raw internal editor.",
			templateButton: "Use template",
			templateSelectedButton: "Current template",
			openMergedStoriesButton: "Open merged stories",
			intakeGuideTitle: "Selected intake contract",
			intakeGuideDescription:
				"This panel spells out what the current template is optimized for, which field matters first, and where the proof boundary still lives.",
			guideLabels: {
				supportLevel: "Support level",
				platform: "Platform",
				sourceType: "Source type",
				adapterType: "Adapter",
				fillNow: "Fill now",
				proofBoundary: "Proof boundary",
			},
			templates: {
				youtubeChannel: {
					title: "YouTube channel",
					description:
						"Strong preset for recurring YouTube intake when you already know the channel ID, handle, or landing URL.",
					fillNow:
						"Start with the channel ID or a stable channel URL, then keep the RSSHub route aligned.",
					proofBoundary:
						"YouTube is a strong path today, but route health still matters if you depend on RSSHub for intake.",
				},
				bilibiliCreator: {
					title: "Bilibili creator",
					description:
						"Strong preset for Bilibili creators when the UID is known and you want a repeatable creator feed.",
					fillNow:
						"Use the creator UID as the primary identifier and keep the companion RSSHub route ready.",
					proofBoundary:
						"Bilibili creator intake is productized, but route breakage or source-side changes still need monitoring.",
				},
				rsshubRoute: {
					title: "RSSHub route",
					description:
						"General preset for wider source coverage when RSSHub can normalize a route into a usable feed.",
					fillNow:
						"Bring a source URL or handle plus the exact RSSHub route you want SourceHarbor to poll.",
					proofBoundary:
						"Do not assume every RSSHub route is equally solid. Treat each route as proven only after it survives real runs.",
				},
				genericRss: {
					title: "Generic RSS feed",
					description:
						"General preset for any source that already exposes a clean RSS or Atom feed without a platform-specific shortcut.",
					fillNow:
						"Paste the exact RSS or Atom feed URL into Source value. Leave Source URL empty unless you want to store the same feed URL explicitly.",
					proofBoundary:
						"Feed quality varies a lot. If the feed is noisy or incomplete, the intake surface should stay honest about that.",
				},
			},
			loadErrorTitle: "Unable to load subscriptions",
			retryCurrentPageButton: "Retry this page",
			editorTitle: "Guided universe editor",
			editorDescription:
				"The selected template pre-fills the intake shape so you can focus on the real source details instead of reconstructing the contract from scratch.",
			formLabels: {
				platform: "Platform",
				sourceType: "Source type",
				sourceValue: "Source value",
				adapterType: "Adapter type",
				sourceUrl: "Source URL (optional)",
				rsshubRoute: "RSSHub route (optional)",
				category: "Category",
				tags: "Tags (comma-separated, optional)",
				priority: "Priority (0-100)",
				enabled: "Enabled",
			},
			placeholders: {
				sourceValue: "Channel ID / UID / URL",
				sourceUrl: "https://example.com/feed.xml",
				rsshubRoute: "/youtube/channel/UCxxxx",
				tags: "ai,weekly,high-priority",
			},
			saveButton: "Save subscription",
			savePending: "Saving...",
			saveStatus: "Saving subscription settings",
			manualIntake: {
				title: "Manual source intake",
				description:
					"Paste URLs, handles, creator pages, or RSSHub routes. Creator-level inputs become subscriptions; direct YouTube/Bilibili video URLs go into today through the current one-off lane.",
				placeholder:
					"https://space.bilibili.com/13416784\nhttps://www.youtube.com/@MindAmend\nhttps://www.youtube.com/watch?v=dQw4w9WgXcQ\n/36kr/newsflashes\nhttps://example.com/feed.xml",
				hint: "One line per input. Bilibili creator pages and YouTube handles save subscriptions; direct video URLs add to today; direct article URLs still return an honest unsupported result.",
				categoryLabel: "Default category",
				tagsLabel: "Tags for new subscriptions (comma-separated, optional)",
				enabledLabel: "Enable created subscriptions immediately",
				submitButton: "Run manual intake",
				submitPending: "Running intake...",
				resultsTitle: "Manual intake results",
				resultsDescription:
					"Each row shows whether the input became a recurring subscription, went into today through the current video lane, or was rejected with an explicit reason.",
				summaryPrefix: "Processed",
				legend: {
					saveSubscription: "Save subscription",
					addToToday: "Add to today",
					unsupported: "Unsupported",
				},
				statusLabels: {
					created: "Created",
					updated: "Updated",
					queued: "Queued",
					reused: "Reused",
					rejected: "Rejected",
				},
				emptyState: "No resolved target",
			},
			currentTitle: "Current subscriptions",
			loadedPrefix: "Loaded",
			loadedSuffix: "subscriptions.",
			currentDescription:
				"Select multiple rows to update categories in bulk. The action bar appears at the bottom.",
			platformOptions: {
				youtube: "YouTube",
				bilibili: "Bilibili",
				rss: "RSS / web source",
			},
			sourceTypeOptions: {
				url: "Source URL",
				youtubeChannelId: "YouTube channel ID",
				bilibiliUid: "Bilibili user UID",
				rsshubRoute: "RSSHub route",
			},
			adapterTypeOptions: {
				rsshubRoute: "RSSHub route",
				rssGeneric: "Generic RSS",
			},
			categoryOptions: {
				misc: "Other",
				tech: "Tech",
				creator: "Creator",
				macro: "Macro",
				ops: "Operations",
			},
		},
		searchPage: {
			metadataTitle: "Search",
			metadataDescription:
				"Grounded search and Ask entry for SourceHarbor, with cited retrieval over digests, transcripts, outlines, and knowledge cards.",
			searchKicker: "SourceHarbor Search Front Door",
			askKicker: "SourceHarbor Ask Front Door",
			searchTitle: "Search",
			askTitle: "Ask your sources",
			searchSubtitle:
				"This is the real operator-facing retrieval surface. It turns digests, transcripts, outlines, and knowledge cards into auditable jumps.",
			askSubtitle:
				"This is a briefing-backed Ask front door. With watchlist context, it can answer with the current story, recent changes, and citations. Without context, it falls back to raw grounded retrieval.",
			searchFormTitle: "Search your sources",
			askFormTitle: "Ask in grounded mode",
			searchFormDescription:
				"`keyword` is the steadiest mode right now. Search already spans strong video sources plus RSS-backed source families, while `semantic` and `hybrid` stay clearly marked as experimental.",
			askFormDescription:
				"Bring a watchlist or briefing context, narrow the question into cited retrieval, then keep the answer, recent changes, and receipts on one page.",
			queryLabel: "Query",
			questionLabel: "Question",
			queryPlaceholder: "agent workflow, retry policy, knowledge cards...",
			questionPlaceholder:
				"What did recent runs say about retry policy, agent workflow, or knowledge cards?",
			searchHint:
				"Every result should jump back into job trace, knowledge, or the source URL.",
			askHint:
				"Attach a watchlist briefing when you want answer + changes + citations. Without context, Ask stays in raw grounded retrieval mode.",
			askContextLabel: "Briefing context",
			askContextTitle: "Context that Ask can stand on",
			askContextDescription:
				"Pick a watchlist or open Ask from Briefings so this page can reuse a real briefing before it looks for question-level evidence.",
			askContextEmptyOption: "No briefing context yet",
			askContextMissingTitle: "Add briefing context first",
			askContextMissingDescription:
				"Ask can still search raw evidence, but it cannot honestly frame an answer-and-change view until you anchor it to a watchlist briefing.",
			askContextTopicLabel: "Story or topic focus",
			askSelectionBasisLabel: "Selected by",
			askSelectionBasis: {
				requested_story_id: "Requested story",
				query_match: "Question match",
				suggested_story_id: "Suggested story",
				first_story: "First visible story",
				none: "No story focus",
			},
			askOpenBriefingButton: "Open selected briefing",
			askClearContextButton: "Clear briefing context",
			askClearStoryContextButton: "Clear story focus",
			modeLabel: "Mode",
			groundingModeLabel: "Grounding mode",
			platformLabel: "Platform",
			platformPlaceholder:
				"youtube, bilibili, rss, rsshub, github, newsletter ...",
			topKLabel: "Top K",
			searchButton: "Search",
			askButton: "Ask",
			clearButton: "Clear",
			platformOptions: {
				all: "All source families",
				youtube: "YouTube",
				bilibili: "Bilibili",
				rss: "RSS / web source",
			},
			modeOptions: {
				keyword: "Keyword",
				semantic: "Semantic (experimental)",
				hybrid: "Hybrid (experimental)",
			},
			searchTruthTitle: "Current truth",
			askTruthTitle: "Grounded Ask mode",
			searchTruthPrimary:
				"Search is a production-facing front door over a real retrieval backend, and the retrieval substrate already reaches beyond two video platforms.",
			searchTruthSecondary:
				"The default picker stays intentionally curated while broader source families continue through the same backend contracts and query surface.",
			askTruthPrimary:
				"What exists today: a briefing-backed answer contract for watchlist-scoped Ask, plus raw retrieval, job trace, knowledge cards, and original source links.",
			askTruthSecondary:
				"What does not exist yet: a global free-form answer engine that works without briefing context or real citations.",
			askTruthNote:
				"Without watchlist context, Ask still stays honest by falling back to grounded retrieval instead of pretending the answer model is universal.",
			askTruthContractLead:
				"Current contract: answer first, recent changes second, cited drill-down third, and operator auditable throughout.",
			searchTruthCta: "Open Ask mode",
			askTruthCta: "Open Ask details",
			openRawSearchButton: "Open raw search",
			askContractArtifactLabel: "Ask contract artifact",
			searchContractTitle: "Result contract",
			askContractTitle: "Best current use",
			searchContractPrimary:
				"Each hit exposes a snippet, source type, score, and jump targets into a job trace, knowledge page, or original source URL.",
			searchContractSecondary:
				"If the corpus is empty, Search should show an honest empty state instead of inventing an answer.",
			askContractPrimary:
				"Use Ask with a watchlist-backed briefing when you want the current answer, the newest change summary, and the evidence trail in one place.",
			askContractSecondary:
				"If you do not attach a watchlist briefing, Ask should stay truthful by dropping back to raw grounded retrieval instead of inventing an answer layer.",
			searchResultsTitle: "Results",
			askResultsTitle: "Grounded result set",
			askErrorTitle: "Ask failed",
			askErrorDescription:
				"The retrieval layer is present, but this question did not return a valid response. Retry before treating the mode as unavailable.",
			askExpectationTitle: "What to expect",
			askExpectationDescription:
				"Use this page when you want to ask in natural language without pretending the system already has a grounded answer model. Every result should point you back to job trace, knowledge cards, or the original source.",
			askSummaryTitle: "Best evidence for your question",
			askSummaryQuestionPrefix: "Question",
			askSummaryHitsPrefix: "Evidence hits",
			askAnswerTitle: "Best current answer",
			askAnswerGroundedState: "Briefing-grounded",
			askAnswerNeedsContextState: "Needs context",
			askAnswerUnavailableState: "Briefing unavailable",
			askAnswerNoConfidentState: "No confident answer yet",
			askAnswerGroundedDescription:
				"SourceHarbor can now answer this as a briefing-aware front door: current answer first, recent change next, receipts underneath.",
			askAnswerContextOnlyDescription:
				"No question is loaded yet, so Ask is showing the current briefing answer before it narrows further.",
			askAnswerUnavailableDescription:
				"The watchlist exists, but the briefing object is unavailable right now, so Ask cannot frame an honest answer layer yet.",
			askAnswerNoConfidentDescription:
				"The selected briefing gives context, but this question did not return enough grounded evidence to claim a confident answer.",
			askAnswerGroundedNote:
				"This answer is grounded in the current watchlist briefing and kept honest by the cited evidence below.",
			askAnswerContextOnlyNote:
				"This is the current briefing answer. Add or refine a question to narrow it into question-level evidence.",
			askAnswerFallbackTitle: "Current briefing answer",
			askAnswerWhyLabel: "Why this is the current answer",
			askStoryFocusTitle: "Story focus driving this answer",
			askStoryFocusDescription:
				"This is the story Ask is currently standing on before it fans out into change tracking and evidence drill-down.",
			askStorySwitcherTitle: "Switch story focus",
			askStorySwitcherDescription:
				"Keep the same question, but pivot the answer layer onto another story from this briefing when you need to compare narratives.",
			askNoEvidenceTitle: "No cited evidence yet",
			askNoEvidenceDescription:
				"Try a narrower question, switch to keyword mode, or process more sources before treating this as a missing capability.",
			askQuestionEvidenceTitle: "Evidence for this question",
			askQuestionEvidenceDescription:
				"These hits come from the current retrieval layer. Use them to verify or challenge the answer above.",
			askCitationsTitle: "Citations behind this answer",
			askCitationsDescription:
				"These are the shortest route back to the exact story, card, compare view, or source that supports the answer above.",
			askOpenCitationRouteButton: "Open cited route",
			askFeaturedRunsDescription:
				"These runs are still the fastest way to inspect the newest receipts behind the current answer.",
			askChangesFallbackDescription:
				"Recent changes only become honest on Ask after a watchlist briefing is attached.",
			askFallbackActionsTitle: "Helpful next steps",
			searchResultsPrefix: "Showing cited retrieval results",
			askResultsPrefix: "Evidence candidates",
			searchRunPrompt: "Run a query to inspect grounded retrieval results.",
			askRunPrompt:
				"Run a grounded question to inspect grounded retrieval results.",
			requestFailed:
				"Current retrieval request failed. Retry first, then inspect API health if it still fails.",
			noResults:
				"No grounded results yet. That usually means the current corpus is empty or the query is too narrow.",
			askResultsAriaLabel: "Ask evidence results",
			groundedEvidenceTitle: "Grounded evidence",
			openJobTraceButton: "Open job trace",
			openKnowledgeCardsButton: "Open knowledge cards",
			openFeedEntryButton: "Open feed entry",
			openSourceButton: "Open source",
			knowledgeCardsSourceLabel: "Knowledge cards",
			experimentalMode: "experimental mode",
		},
		watchlistsPage: {
			metadataTitle: "Watchlists",
			metadataDescription:
				"Persisted SourceHarbor watchlists for topics, claim kinds, platforms, and source matchers, with notification readiness and trend follow-through.",
			kicker: "SourceHarbor Compounders",
			heroTitle: "Watchlists",
			heroSubtitle:
				"Treat this like a long-horizon tracking ledger. You are not searching once and leaving; you are pinning the topics, claims, or sources worth returning to.",
			saveTitle: "Save a watchlist",
			saveDescription:
				"Current matchers cover `topic_key`, `claim_kind`, `platform`, and `source_match`. Wave 1 focuses on persistent tracking first, then deeper external alerting later.",
			nameLabel: "Name",
			namePlaceholder:
				"Retry policy, AI workflow, YouTube AI channel, Claude Code updates...",
			watchTypeLabel: "Watch type",
			matcherValueLabel: "Matcher value",
			matcherValuePlaceholder:
				"retry-policy, claim_kind, youtube, /channel-name, codex, claude-code ...",
			deliveryLabel: "Delivery",
			enabledLabel: "Enabled",
			saveButton: "Save watchlist",
			updateButton: "Update watchlist",
			createNewButton: "Create new",
			openTrendViewButton: "Open merged story view",
			openBriefingButton: "Open briefing",
			alertTitle: "Alert readiness",
			alertDescription:
				"SourceHarbor can already persist watchlists and reuse them inside the dashboard. Whether external alerts are ready depends on the notification gate, not on whether the form submission succeeds.",
			alertFallback:
				"Notification readiness is unavailable right now. Keep using dashboard tracking first.",
			openNotificationSettingsButton: "Open notification settings",
			currentTitle: "Current watchlists",
			currentDescription:
				"These are real persisted tracking objects, not a UI shell. You can save them, read them back, and route them into the trend view today.",
			currentError:
				"Unable to load watchlists right now. Check API health, then retry this page.",
			currentEmpty:
				"There are no watchlists yet. Save one topic or source first so this page becomes a tracking console instead of an empty form.",
			updatedPrefix: "Updated",
			enabledState: "enabled",
			pausedState: "paused",
			editButton: "Edit",
			viewTrendButton: "View trend",
			deleteButton: "Delete",
			recentMovementTitle: "Recent movement",
			recentMovementDescription:
				"Start with the latest three movements to decide whether this watchlist is worth following. The fuller continuity view lives on the trend page.",
			openJobButton: "Open job",
			matchedCardsPrefix: "matched cards",
			addedTopicsPrefix: "Added topics",
			removedTopicsPrefix: "Removed topics",
			noneValue: "none",
			matcherOptions: {
				topicKey: "Topic key",
				claimKind: "Claim kind",
				platform: "Platform",
				sourceMatch: "Source match",
			},
			deliveryOptions: {
				dashboard: "Dashboard only",
				email: "Email when ready",
			},
		},
		trendsPage: {
			metadataTitle: "Trends",
			metadataDescription:
				"Cross-run trend and merged story view for SourceHarbor watchlists, showing how repeated themes are converging across multiple sources and recent evidence runs.",
			kicker: "SourceHarbor Trends",
			heroTitle: "Merged source stories",
			heroSubtitle:
				"This is where repeated watchlist hits start looking like a product surface instead of scattered diffs. The merged story stays visible, and the raw run receipts remain right below it.",
			chooseTitle: "Choose a watchlist",
			chooseDescription:
				"Pick one watchlist to inspect source coverage, merged stories, and the latest evidence runs without pretending the system already has a magical global narrative layer.",
			empty:
				"Save at least one watchlist first so this page can show real merged stories instead of an empty selector.",
			matcherLabel: "Matcher",
			recentRunsLabel: "Recent runs",
			matchedCardsLabel: "Matched cards",
			sourceCoverageTitle: "Source coverage",
			sourceCoverageDescription:
				"These are the source families currently feeding this watchlist, based on real matched runs and cards.",
			sourceCoverageRunsLabel: "Runs",
			sourceCoverageCardsLabel: "Matched cards",
			mergedStoriesTitle: "Merged stories",
			mergedStoriesDescription:
				"Each card below groups the same topic or claim across multiple runs so the repeated story becomes visible without hiding the underlying receipts.",
			mergedStoriesEmpty:
				"No repeated topic or claim group is visible yet. As more runs land, this page will start surfacing the repeated story here.",
			sourceCountLabel: "Sources",
			runCountLabel: "Runs",
			latestSeenLabel: "Latest seen",
			recentEvidenceTitle: "Recent evidence runs",
			recentEvidenceDescription:
				"Keep the raw run-by-run movement in view so every merged story stays auditable.",
			openBriefingButton: "Open briefing",
			editWatchlistButton: "Edit watchlist",
			openJobButton: "Open job",
			openKnowledgeButton: "Open knowledge",
			openSourceButton: "Open source",
			addedTopicsPrefix: "Added topics",
			removedTopicsPrefix: "Removed topics",
			addedClaimKindsPrefix: "Added claim kinds",
			removedClaimKindsPrefix: "Removed claim kinds",
			noneValue: "none",
		},
		briefingsPage: {
			metadataTitle: "Briefings",
			metadataDescription:
				"Unified watchlist briefing surface for SourceHarbor, showing what the current story is, what changed, and which evidence to inspect next.",
			kicker: "SourceHarbor Briefings",
			heroTitle: "Unified briefings",
			heroSubtitle:
				"Start with the current story, then inspect what changed, then drill into the receipts. This is the smallest truthful unified story line built on watchlists, merged stories, jobs, and knowledge.",
			truthTitle: "Truthful product line",
			truthDescription:
				"This page reuses real watchlists, merged stories, and evidence links. It is not claiming a fully automatic cross-source fusion engine yet.",
			truthPrimary:
				"Think of it like a daily briefing board: first the lead paragraph, then the deltas, then the documents underneath.",
			truthSecondary:
				"It stays grounded in watchlists, jobs, knowledge cards, and original sources so you can keep checking the receipts.",
			openWatchlistsButton: "Open watchlists",
			openTrendsButton: "Open trends",
			chooseTitle: "Choose a briefing",
			chooseDescription:
				"Pick a watchlist to load the corresponding briefing object. The front door is unified, but the underlying tracking object is still explicit.",
			empty:
				"Save at least one watchlist first so this page can load a real briefing instead of an empty shell.",
			unavailableTitle: "Briefing unavailable",
			unavailableDescription:
				"The selected watchlist exists, but its briefing object is unavailable right now. Retry after the API route is ready or the backend response recovers.",
			overviewTitle: "What the story is saying now",
			overviewDescription:
				"Read this first. It is the operator summary for what multiple sources are currently repeating about the same thing.",
			sourcesLabel: "Sources",
			runsLabel: "Runs",
			storiesLabel: "Story groups",
			matchedCardsLabel: "Matched cards",
			latestSeenLabel: "Latest seen",
			generatedLabel: "Generated",
			currentWatchlistLabel: "Current watchlist",
			matcherLabel: "Matcher",
			primaryStoryLabel: "Lead story",
			signalsTitle: "Current signals",
			noSignals: "No highlighted signals yet.",
			openTrendButton: "Open trend view",
			editWatchlistButton: "Edit watchlist",
			askBriefingButton: "Ask this briefing",
			differencesTitle: "What changed recently",
			differencesDescription:
				"Use this like the delta section of a briefing memo. Each row points at a change worth checking instead of forcing you to diff every run by hand.",
			differencesEmpty:
				"No highlighted differences yet. As the briefing route matures, this section will surface the newest meaningful changes here.",
			addedTopicsLabel: "Added topics",
			removedTopicsLabel: "Removed topics",
			addedClaimKindsLabel: "Added claim kinds",
			removedClaimKindsLabel: "Removed claim kinds",
			newStoryKeysLabel: "New story keys",
			removedStoryKeysLabel: "Removed story keys",
			compareTitle: "Compare excerpt",
			noCompareExcerpt: "No compare excerpt is available yet.",
			openCompareButton: "Open compare",
			changeJobsLabel: "Jobs behind this change",
			openJobButton: "Open job",
			noneValue: "none",
			evidenceTitle: "Evidence drill-down",
			evidenceDescription:
				"Every evidence card keeps the receipt trail open so you can jump back to job trace, knowledge cards, or the original source without leaving the briefing.",
			evidenceEmpty:
				"No evidence cards are attached yet. The summary can exist before the drill-down is populated.",
			storyEvidenceTitle: "Story evidence",
			featuredRunsTitle: "Featured runs",
			askStoryButton: "Ask about this story",
			openKnowledgeButton: "Open knowledge",
			openSourceButton: "Open source",
			openBriefingButton: "Open briefing",
			unknownStoryLabel: "Unlabeled story",
			untitledEvidenceLabel: "Untitled evidence",
			noExcerpt: "No excerpt available yet.",
			platformUnknown: "Unknown platform",
		},
		proofPage: {
			metadataTitle: "Proof",
			metadataDescription:
				"SourceHarbor proof boundary for product surface, local supervisor proof, long live-smoke lanes, and remote proof expectations.",
			kicker: "SourceHarbor Proof",
			heroTitle: "Proof boundary",
			heroSubtitle:
				"Treat this as the master switch for what SourceHarbor can say confidently now and what still needs extra evidence. Code, docs, local runtime, and remote proof are not the same ledger.",
			nextTruthfulJumpsTitle: "Next truthful jumps",
			nextTruthfulJumpsDescription:
				"These jumps are already real surfaces. They are not decorative packaging.",
			openCommandCenterButton: "Open command center",
			openOpsButton: "Open Ops inbox",
			openMcpButton: "Open MCP quickstart",
			openBuildersButton: "Open builder guide",
			openStatusButton: "Open project status",
			layers: {
				productSurfaceTitle: "Product surface",
				productSurfaceBody:
					"README, runtime-truth, project-status, Search, Ask, MCP, and Ops explain what SourceHarbor is and where each claim lives.",
				localSupervisorTitle: "Local supervisor proof",
				localSupervisorBody:
					"`bootstrap -> up -> status -> doctor` proves the repo-managed local stack, with routes taken from `resolved.env` instead of assumed defaults.",
				longSmokeTitle: "Long live-smoke lane",
				longSmokeBody:
					"`./bin/smoke-full-stack --offline-fallback 0` is stricter than the base local proof and can still stop on provider-side YouTube, Resend, or Gemini gates.",
				remoteProofTitle: "Remote proof",
				remoteProofBody:
					"Release badges, GitHub settings, and external distribution claims still need fresh remote verification. Local success does not replace that layer.",
			},
		},
		playgroundPage: {
			metadataTitle: "Playground",
			metadataDescription:
				"Read-only SourceHarbor playground built on clearly labeled sample corpus, example jobs, retrieval results, and bundle shape.",
			kicker: "SourceHarbor Playground",
			heroTitle: "Read-only sample playground",
			heroSubtitle:
				"This page uses a clearly labeled sample corpus, not live production results. Its job is to let you feel the product value before wiring the whole stack.",
			boundaryDescription:
				"Sample boundary: this playground is read-only and sample-labeled. Do not treat it as current operator state, current `main` proof, or remote proof.",
			openSearchButton: "Open real Search",
			openProofButton: "Open proof ladder",
			sampleSourcesTitle: "Sample sources",
			exampleJobsTitle: "Example jobs",
			retrievalResultsTitle: "Example retrieval results",
			exampleWatchlistsTitle: "Example watchlists and trend",
			recentRunsLabel: "Recent runs",
			exampleBundleTitle: "Example bundle shape",
			exampleBundleDescription:
				"Use this as a mental model for what a shareable internal evidence bundle looks like. It is a sample, not a live export.",
		},
		jobsPage: {
			metadataTitle: "Job Trace",
			metadataDescription:
				"Inspect SourceHarbor job trace, compare runs, review evidence bundles, and follow long-lived knowledge cards back to the underlying pipeline work.",
			kicker: "SourceHarbor Job Trace",
			heroTitle: "Job Trace",
			heroSubtitle:
				"Look up a job ID to inspect full pipeline state, compare drift, and trace evidence bundles without leaving the operator surface.",
			findTitle: "Find a job",
			findDescription:
				"Enter a job ID to inspect the step trail and artifact links. You can jump here from recent videos on the home page or the digest feed.",
			findDescriptionPrefix:
				"Enter a job ID to inspect the step trail and artifact links. You can jump here from",
			homeLinkLabel: "recent videos on the home page",
			findDescriptionConnector: "or",
			digestFeedLinkLabel: "the digest feed",
			findDescriptionSuffix: ".",
			jobIdLabel: "Job ID *",
			jobIdPlaceholder: "9be4cbe7-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
			searchButton: "Search",
			compareTitle: "Compare to previous run",
			compareDescription:
				"Treat this as the answer to how much the latest run changed compared with the previous one. If there is no prior successful job, the page should say so plainly.",
			knowledgeTitle: "Knowledge cards",
			knowledgeDescription:
				"Treat these as long-lived cards extracted from this run. They are meant to be more reusable than the raw digest itself.",
			lookupFailedTitle: "Lookup failed",
			retryCurrentPageButton: "Retry current page",
			currentStatusPrefix: "Current job status",
			pipelineStatusPrefix: "pipeline status",
			acrossStepsSuffix: "steps",
			jobOverviewTitle: "Job overview",
			overviewFields: {
				jobId: "Job ID",
				videoId: "Video ID",
				status: "Status",
				finalPipelineStatus: "Final pipeline status",
				createdAt: "Created at",
				updatedAt: "Updated at",
			},
			viewInDigestFeed: "View in digest feed",
			downloadEvidenceBundle: "Download evidence bundle",
			evidenceBundleNote:
				"Evidence bundles are for internal reuse and async collaboration. They are not public release proof.",
			stepSummaryTitle: "Step summary",
			stepSummaryEmpty: "No step records yet.",
			stepSummaryCaption: "Job step summary table",
			stepSummaryHeaders: {
				step: "Step",
				status: "Status",
				retries: "Retries",
				startedAt: "Started at",
				finishedAt: "Finished at",
			},
			compareFields: {
				previousJob: "Previous job",
				addedLines: "Added lines",
				removedLines: "Removed lines",
			},
			compareDiffEmpty: "No line-level diff preview was produced.",
			compareEmpty:
				"No previous successful job is available for comparison yet.",
			knowledgeEmpty: "No knowledge cards generated yet.",
			degradationsTitle: "Degradations",
			degradationsEmpty: "No degradations recorded.",
			unknownValue: "unknown",
			naValue: "n/a",
			artifactIndexTitle: "Artifact index",
			artifactsEmpty: "No artifacts yet.",
			opensInNewTabSuffix: "(opens in a new tab)",
		},
		useCasesPage: {
			kicker: "SourceHarbor Use Case",
			whyTitle: "Why this page exists",
			whyDescription:
				"These use-case pages are discoverability surfaces, not hosted product promises. Every claim here should route back to a real SourceHarbor capability.",
			nextStepsTitle: "Next truthful steps",
			nextStepsDescription:
				"Use these links to move from copy into real product surfaces, proof, or sample playgrounds.",
			proofCta: "Open proof ladder",
			builderTitle: "Builder fit",
			builderDescription:
				"Treat these pages as truthful fit guides for Codex, Claude Code, MCP clients, and source-first builder workflows.",
		},
		builderSurfaces: {
			title: "Build with Codex, Claude Code, and MCP clients",
			subtitle:
				"Use SourceHarbor as an agent-facing control tower through MCP, the HTTP API, the thin repo-local CLI facade, and the shared TypeScript client layer.",
			mcpCta: "Open MCP quickstart",
			codexCta: "Open Codex workflow",
			claudeCodeCta: "Open Claude Code workflow",
			proofCta: "Inspect proof ladder",
			researchCta: "Open research pipeline",
			resourceTitle: "Open the builder doors that already ship today",
			resourceDescription:
				"These are the fastest repo-backed handoff points when you want docs, starter packs, or package-level entry surfaces instead of only the in-app story.",
			buildersGuideCta: "Open builders guide",
			starterPacksCta: "Open starter packs",
			cliPackageCta: "Inspect CLI package",
			sdkPackageCta: "Inspect TypeScript SDK",
			highlightPills: [
				"MCP-native",
				"Codex-ready",
				"Claude Code-ready",
				"HTTP API",
				"Thin repo CLI",
				"Proof-first",
			],
			cards: {
				reuse: {
					title: "One control plane, four real doors",
					description:
						"Web, HTTP API, MCP, and the thin repo-local CLI facade all point to the same jobs, artifacts, grounded search, and operator truth.",
					bullets: [
						"Search + Ask",
						"MCP + API",
						"Thin repo CLI",
						"Shared TypeScript client",
					],
				},
				proof: {
					title: "Receipts before vibes",
					description:
						"Proof, runtime truth, and project status explain what is already real, what is gated, and what is still a deliberate bet.",
					bullets: ["Proof boundary", "Runtime truth", "Project status"],
				},
				compounders: {
					title: "Worth coming back to",
					description:
						"Watchlists, trends, bundles, and the sample playground make SourceHarbor feel like a reusable research product instead of a one-shot summarizer.",
					bullets: ["Watchlists", "Trends", "Bundles"],
				},
			},
		},
	},
	"zh-CN": {
		common: {
			close: "关闭",
		},
		routeTransition: {
			announcementPrefix: "Switched to:",
			labels: {
				home: "Home",
				subscriptions: "Subscriptions",
				search: "Search",
				ask: "Ask",
				mcp: "MCP Quickstart",
				ops: "Ops inbox",
				reader: "Reader",
				watchlists: "Watchlists",
				trends: "Trends",
				briefings: "Briefings",
				playground: "Playground",
				proof: "Proof",
				knowledge: "Knowledge",
				jobs: "Jobs",
				ingestRuns: "Ingest runs",
				feed: "Digest feed",
				settings: "Settings",
				useCases: "Use cases",
				page: "Page",
			},
		},
		formValidation: {
			required: "请先填写并修正必填项后再提交。",
			requireOne: "请至少填写一项必填来源后再提交。",
			requireOneExclusive: "当前只能填写一项来源，请清空多余输入后再提交。",
		},
		loading: {
			app: { title: "页面加载中", message: "正在加载首页内容，请稍候。" },
			feed: {
				title: "Digest feed loading",
				message: "Loading the digest feed. Please wait.",
			},
			jobs: {
				title: "Job trace loading",
				message: "Loading job details. Please wait.",
			},
			settings: {
				title: "设置加载中",
				message: "正在加载设置项，请稍候。",
			},
			subscriptions: {
				title: "Loading subscriptions",
				message: "Loading subscription data. Please wait.",
			},
		},
		submitButton: {
			defaultPendingLabel: "提交中…",
			pendingBadge: "处理中",
			pendingSrOnly: "正在提交，请稍候。",
		},
		syncNow: {
			idle: {
				buttonLabel: "立即同步",
				badgeLabel: "待命",
				statusLabel: "待命：点击后立即同步最新内容。",
			},
			loading: {
				buttonLabel: "同步中…",
				badgeLabel: "同步中",
				statusLabel: "正在拉取与分析新内容，请稍候。",
				liveStatusLabel: "正在同步，请稍候。",
				retryTitle: "同步失败，按 Enter 或空格可再次尝试。",
			},
			done: {
				buttonLabel: "同步完成",
				badgeLabel: "已完成",
				statusLabel: "同步完成，列表即将刷新。",
				liveStatusLabel: "同步完成，列表正在刷新。",
			},
			error: {
				buttonLabel: "同步失败，重试",
				badgeLabel: "需重试",
				statusLabel: "同步失败，请检查网络后重试。",
				liveStatusLabel: "同步失败，请检查网络后重试。",
				retryTitle: "同步失败，按 Enter 或空格可再次尝试。",
			},
		},
		relativeTime: {
			soon: "马上",
			tomorrow: "明天",
			justNow: "刚刚",
			minuteFuture: "{count} 分钟后 | {count} 分钟后",
			hourFuture: "{count} 小时后 | {count} 小时后",
			dayFuture: "{count} 天后 | {count} 天后",
			weekFuture: "{count} 周后 | {count} 周后",
			monthFuture: "{count} 个月后 | {count} 个月后",
			yearFuture: "{count} 年后 | {count} 年后",
			minutePast: "{count} 分钟前 | {count} 分钟前",
			hourPast: "{count} 小时前 | {count} 小时前",
			dayPast: "{count} 天前 | {count} 天前",
			weekPast: "{count} 周前 | {count} 周前",
			monthPast: "{count} 个月前 | {count} 个月前",
			yearPast: "{count} 年前 | {count} 年前",
			absoluteLocale: "zh-CN",
		},
		dashboard: {
			metadataTitle: "首页",
			metadataDescription:
				"SourceHarbor command center，用一个 operator-facing control tower 管 AI knowledge intake、grounded retrieval、ops triage 与 builder entry。",
			kicker: "SourceHarbor Command Center",
			heroTitle: "AI 知识控制塔",
			heroSubtitle:
				"从一个面向运营者的 command center 里运行采集、grounded retrieval、任务编排和 agent reuse。",
			frontDoors: {
				subscriptionsTitle: "Source-universe intake",
				subscriptionsDescription:
					"先从 YouTube / Bilibili 的强支持模板起步，再扩到 RSSHub route 和通用 RSS，但不要把所有 route 都说成已经证明稳定。",
				subscriptionsCta: "打开 Subscriptions",
				subscriptionsHint:
					"同一份 template catalog 现在同时驱动 Web、API 和 MCP intake。",
				searchTitle: "搜索入口",
				searchDescription:
					"从一个面向运营者的入口里检索 digest、知识卡片、转写和相关证据。",
				searchCta: "打开 Search",
				knowledgeCta: "打开 Knowledge",
				askTitle: "向来源提问",
				askDescription:
					"带着 briefing-backed story 上下文进入 answer、changes 和 evidence，而不是停在原始 retrieval 命中上。",
				askCta: "打开 Ask",
				briefingsCta: "打开 Briefings",
				askHint:
					"Ask 现在会复用与 Briefings 共用的 server-owned story payload，而不是再拼一套浏览器侧 view model。",
				mcpTitle: "MCP 入口",
				mcpDescription:
					"通过 MCP 复用同一套 intake、story、job 与 retrieval 真相，而不是再造第二层 agent surface。",
				mcpCta: "打开 MCP quickstart",
				jobCta: "查看 job 证据",
			},
			sectionHeadings: {
				whyNow: "为什么值得继续看",
				firstHop: "先选第一条路径",
				primaryFrontDoors: "核心入口",
				builderEntryPoints: "Builder 入口",
				compounderSurfaces: "复利层",
				keyMetrics: "控制塔指标",
			},
			whyNow: {
				sharedTruthTitle: "Web、API 和 MCP 读的是同一套真相",
				sharedTruthDescription:
					"运营者和 agent builder 看到的是同一批 jobs、artifacts 和 retrieval 状态，而不是三套互相打架的产品壳。",
				proofFirstTitle: "Proof 和产品故事贴在一起",
				proofFirstDescription:
					"README、proof、runtime truth 和 job receipts 讲的是同一份合同，所以新来的人能先建立信任，再决定是否完整跑起来。",
				returnLoopTitle: "不是跑一次就结束的 summarizer",
				returnLoopDescription:
					"Watchlists、trends、briefings、bundles 和 playground 让 SourceHarbor 更像会持续复用的控制塔，而不是一次性的摘要脚本。",
			},
			firstHop: {
				evaluateTitle: "先判断这个产品是不是真的",
				evaluateDescription:
					"先看最快的 no-boot 预览，再读 proof ladder，确定它不是靠气氛撑起来的，然后再决定要不要完整本地启动。",
				evaluatePrimaryCta: "打开 no-boot tour",
				evaluateSecondaryCta: "打开 proof ladder",
				operateTitle: "把 SourceHarbor 当成 operator 产品来跑",
				operateDescription:
					"先走最短的本地真实路径，起来以后再进入 subscriptions、search 和 ops，不要一上来就试图理解所有门。",
				operatePrimaryCta: "打开 start-here 指南",
				operateSecondaryCta: "从 Subscriptions 开始",
				operateTertiaryCta: "打开 Ops inbox",
				buildTitle: "基于同一套系统真相继续构建",
				buildDescription:
					"如果你来这里是为了接入，而不是先当 operator 用，就直接进 MCP、builders 文档和 distribution status。",
				buildPrimaryCta: "打开 MCP quickstart",
				buildSecondaryCta: "打开 builders 指南",
				buildTertiaryCta: "打开 distribution status",
			},
			compounders: {
				watchlistsTitle: "Watchlists 是 tracking object",
				watchlistsDescription:
					"先在这里保存 watchlist，再去 Trends 看统一信息面，不要把两个页面当成同一种角色。",
				watchlistsCta: "打开 Watchlists",
				trendsTitle: "Trends 是 compounder 前门",
				trendsDescription:
					"当你想先看“多次运行里反复出现的主线”时，先来这里：上面是 merged stories，下面是 recent evidence runs，再继续跳到 Briefings 或 Jobs。",
				trendsCta: "打开 Trends",
				briefingsTitle: "Briefings 是 shared story surface",
				briefingsDescription:
					"Briefings 先降认知负担：先看当前 story，再看 delta，最后 drill-down 到证据；Ask 会复用同一条 selected-story truth。",
				briefingsCta: "打开 Briefings",
				bundleTitle: "证据包",
				bundleDescription:
					"把一次运行继续带走，作为内部 bundle 复用 digest、trace summary、knowledge cards 和 artifact manifest，而不是在聊天里贴截图。",
				bundleCta: "打开 Job Trace",
				bundleHint: "可从任意 job 详情页下载 bundle。",
				playgroundTitle: "Playground 保持 sample-proof",
				playgroundDescription:
					"查看清楚标注的 sample-proof lane；真要看当前 operator truth，就跳回 live 前门。",
				playgroundCta: "打开 Playground",
				proofCta: "打开 Proof",
				useCasesCta: "打开 use case 页面",
			},
			loadErrorTitle: "当前无法加载 command center",
			retryCurrentPage: "重试当前页面",
			metricsRegionLabel: "关键指标",
			metrics: {
				subscriptions: {
					title: "订阅数",
					unavailable: "订阅数数据暂不可用",
					emptyCta: "添加第一个订阅 →",
				},
				discoveredVideos: {
					title: "已发现视频",
					unavailable: "已发现视频数据暂不可用",
				},
				runningJobs: {
					title: "运行中 / 排队",
					unavailable: "运行中和排队任务数据暂不可用",
				},
				failedJobs: {
					title: "失败任务",
					unavailable: "失败任务数据暂不可用",
					openFailed: "查看失败任务 →",
					openOps: "打开 Ops inbox →",
				},
				unavailableOutput: "数据暂不可用",
			},
			pollIngest: {
				title: "拉取订阅",
				description:
					"创建新的 ingest run，再跳到 jobs 和 traces，而不是靠猜测判断 intake 是否真的启动。",
				platformLabel: "平台（可选）",
				maxNewVideosLabel: "最多拉取视频数",
				submit: "触发采集",
				submitPending: "触发中…",
				submitStatus: "正在创建新的 ingest run，请稍候。",
				queueLink: "查看任务队列 →",
			},
			processVideo: {
				title: "处理单个来源",
				description:
					"把一个 source URL 放进 pipeline，再去看 trace、artifacts 和 retrieval surface。",
				platformLabel: "平台 *",
				urlLabel: "来源链接 *",
				modeLabel: "模式 *",
				forceLabel: "强制重跑",
				submit: "开始处理",
				submitPending: "创建任务中…",
				submitStatus: "正在创建新的处理任务，请稍候。",
				jobDetailLink: "查看任务详情 →",
			},
			ingestRuns: {
				title: "最近摄取运行",
				description:
					"把它理解成收货台账。如果你刚触发了 intake，这里应该先告诉你 run 有没有真的动起来。",
				viewAll: "查看全部摄取运行 →",
				unavailable: "摄取运行数据暂不可用。",
				empty: "暂无摄取运行。",
				caption: "最近摄取运行列表",
				platform: "平台",
				status: "状态",
				newJobs: "新任务",
				candidates: "候选条目",
				allPlatforms: "全部",
			},
			recentVideos: {
				title: "最近视频",
				description:
					"这里只展示最近 10 条视频。想看完整运行历史，请直接跳到 job trace。",
				viewAll: "查看全部任务 →",
				empty: "暂无视频。",
				unavailable: "当前无法加载视频列表。",
				caption: "最近视频列表",
				titleColumn: "标题",
				platformColumn: "平台",
				statusColumn: "状态",
				lastJobColumn: "最近任务",
			},
			pollPlatformOptions: {
				all: "全部",
			},
			processModeOptions: {
				full: "完整运行",
				textOnly: "纯文本",
				refreshComments: "刷新评论",
				refreshLlm: "刷新 LLM 输出",
			},
		},
		ops: {
			metadataTitle: "Ops Inbox",
			metadataDescription:
				"SourceHarbor 的 operator inbox，用来查看 failures、provider health、delivery readiness 与下一步动作。",
			kicker: "SourceHarbor Ops",
			heroTitle: "运营诊断",
			heroSubtitle:
				"打开给值班者看的异常队列：失败任务、provider health、delivery readiness，以及接下来该做什么。",
			loadErrorTitle: "当前无法汇总 Ops 诊断",
			loadErrorDescription:
				"请先确认 API health 和本地 full-stack 状态，再重试当前页面。",
			partialDataTitle: "部分诊断数据暂不可用",
			partialDataDescription:
				"这页会保留已经加载成功的条目。先看 API health 和 doctor，再决定是否重跑完整 Ops 拉取。",
			backToDashboard: "返回 command center",
			summary: {
				attentionItems: {
					title: "待处理异常",
					description: "当前需要人工值班处理的总条数。",
				},
				failedJobs: {
					title: "失败任务",
					description:
						"这些任务应该优先把你送回 job trace，而不是先去别的地方猜。",
				},
				failedIngest: {
					title: "失败摄取",
					description: "没有发车或半路失败的 ingest 批次。",
				},
				notificationGate: {
					title: "通知 / Gate",
					description:
						"通知 readiness、provider health 和 hardening gate 的合计。",
				},
			},
			inbox: {
				title: "Ops inbox",
				description:
					"把它理解成值班收件箱。每条异常都给一个主跳转，不逼你先猜该去哪个台账。",
				empty:
					"当前没有需要值班处理的异常。最近任务、摄取运行和通知链路都在可接受范围内。",
			},
			nextSteps: {
				title: "推荐下一步",
				description:
					"把它理解成值班副驾驶。这里把 gate 和 inbox 异常翻译成接下来几步动作，而不是逼你先自己读完所有表格。",
				noActions:
					"当前没有紧急下一步动作。若还需要继续巡检，可直接查看 provider health 或 notification readiness。",
				triagePrefix: "处理 inbox 项",
				gatePrefix: "检查 hardening gate",
				openAction: "打开动作",
			},
			providerHealth: {
				title: "Provider health",
				description:
					"这是快速判断系统整体有没有歪掉的视图。黄色表示需要人工复核，红色表示最近有明确失败。",
				empty: "当前没有 provider health 异常记录。",
				defaultMessage: "当前 provider health 需要人工复核。",
			},
			notificationReadiness: {
				title: "Notification readiness",
				description:
					"把“配置没填好”和“发送失败”拆开看，避免把两类问题混成一句“通知坏了”。",
				empty: "当前没有待处理的 notification deliveries。",
			},
		},
		settings: {
			metadataTitle: "设置",
			metadataDescription:
				"管理 SourceHarbor 的通知投递、日报时机、failure alerts 与 test-send controls。",
			kicker: "SourceHarbor Settings",
			heroTitle: "通知设置",
			heroSubtitle:
				"从一个 operator surface 里管理摘要投递、失败告警和测试发送行为。",
			loadErrorTitle: "当前无法加载设置",
			retryCurrentPage: "重试当前页面",
			configSectionTitle: "通知配置",
			configDates: "创建时间：{createdAt} | 更新时间：{updatedAt}",
			enabledLabel: "启用通知",
			toEmailLabel: "收件人邮箱",
			dailyDigestLabel: "启用每日摘要",
			dailyDigestHourLabel: "每日摘要发送时间（UTC 小时）",
			dailyDigestHint:
				"本地时间预览：这个字段使用 UTC 小时。保存前请先把本地目标时间换算成 UTC。",
			failureAlertLabel: "启用失败告警",
			saveButton: "保存配置",
			savePending: "保存中…",
			saveStatus: "正在保存通知配置，请稍候。",
			testSectionTitle: "发送测试通知",
			testRecipientDescription: "当前默认收件人：{email}",
			testRecipientMissing:
				"当前默认收件人尚未设置。请先在上方填写，再发送测试通知。",
			overrideRecipientLabel: "覆盖收件人（可选）",
			overrideRecipientPlaceholder: "留空则使用已配置的收件人",
			subjectLabel: "主题（可选）",
			subjectPlaceholder: "SourceHarbor 测试通知",
			bodyLabel: "正文（可选）",
			bodyPlaceholder: "这是一封来自 SourceHarbor 的测试通知。",
			sendButton: "发送测试邮件",
			sendPending: "发送中…",
			sendStatus: "正在发送测试通知，请稍候。",
		},
		mcpPage: {
			metadataTitle: "MCP",
			metadataDescription:
				"SourceHarbor 的 MCP quickstart，说明真实启动命令、代表性工具，以及它与 API / Web 的关系。",
			kicker: "SourceHarbor MCP Front Door",
			heroTitle: "MCP Quickstart",
			heroSubtitle:
				"把它理解成 agent-facing control plane。Web 服务运营者，API 服务系统集成，MCP 服务助手和工作流，而三者都指向同一套 pipeline。",
			startTitle: "一条命令本地启动",
			startDescription:
				"MCP 不是第二套业务逻辑。先用薄的 repo-local CLI 门面找路，再通过 MCP 启动同一套 API-backed system。",
			startNote:
				"`./bin/sourceharbor mcp` 会路由到接在 apps/mcp/server.py 上的同一台 FastMCP server。`./bin/dev-mcp` 仍然是底层直达入口。",
			toolsTitle: "代表性工具",
			toolsDescription: "这些已经足够在三分钟内解释清楚当前 surface。",
			relationshipTitle: "MCP 与其他产品面的关系",
			relationshipDescription:
				"Web 是 operator-facing command center。API 是共享契约。MCP 是 agent-facing surface。SourceHarbor 会先经过 API，而不是让工具直接打数据库。",
			searchCta: "打开 Search",
			askCta: "打开 Ask",
		},
		knowledgePage: {
			metadataTitle: "Knowledge",
			metadataDescription:
				"SourceHarbor 的 knowledge layer，承载提取后的 knowledge cards、job-linked evidence 与可复用资产。",
			kicker: "SourceHarbor Knowledge Layer",
			heroTitle: "Knowledge",
			heroSubtitle:
				"把它理解成从 digest 里提炼出来的长期资产层。这里更像知识卡片柜，而不是一次性的阅读流。",
			filterTitle: "筛选知识卡片",
			filterDescription:
				"用 job、video、card type、topic 和 claim 过滤器先缩小范围，再查看具体卡片。",
			filterLabels: {
				jobId: "Job ID",
				videoId: "Video ID",
				cardType: "Card type",
				topic: "Topic",
				claimKind: "Claim kind",
				limit: "Limit",
			},
			idPlaceholder: "11111111-1111-1111-1111-111111111111",
			filterButton: "筛选",
			clearButton: "清空",
			totalCards: "总卡片数",
			uniqueJobs: "唯一任务数",
			cardTypes: "卡片类型",
			sectionTitle: "知识卡片",
			sectionDescription:
				"这里展示最近抽取出的知识卡片。需要完整上下文时，请跳回 Job Trace。",
			loadError: "当前无法加载知识卡片。",
			empty: "暂无知识卡片。",
			jobTraceCta: "Job Trace",
			openJobTraceButton: "Open job trace",
			openJobTraceAriaPrefix: "Open job trace for",
			sameTypeButton: "Same type",
			metaLabels: {
				job: "Job",
				video: "Video",
				order: "Order",
				topic: "Topic",
			},
		},
		ingestRunsPage: {
			metadataTitle: "Ingest Runs",
			metadataDescription:
				"SourceHarbor 的 intake ledger，用来查看最近 ingest runs、candidate 数量、job 创建与 batch 详情。",
			kicker: "SourceHarbor Intake",
			heroTitle: "Ingest Runs",
			heroSubtitle:
				"把它理解成摄取台账。这里会告诉你每次拉取是否真的发车、发现了多少候选、又创建了多少任务。",
			filterTitle: "查找一次 ingest run",
			filterDescription:
				"输入 run ID 可以查看某次摄取批次；留空时显示最近的批次列表。",
			runIdLabel: "Run ID",
			runIdPlaceholder: "11111111-1111-1111-1111-111111111111",
			searchButton: "Search",
			loadErrorTitle: "加载失败",
			loadErrorDescription: "当前无法加载 ingest runs。",
			sectionTitle: "最近摄取运行",
			sectionDescription:
				"最近 10 次 intake 批次，方便快速判断当前 source intake 是否还在动。",
			platform: "平台",
			status: "状态",
			jobs: "任务数",
			candidates: "候选条目",
			created: "创建时间",
			allPlatforms: "全部",
			empty: "暂无 ingest runs。",
			detailTitle: "Run 详情",
			detailDescription: "这一块更像本次 ingest batch 的详细账单。",
			detailEmpty: "当前 run 还没有 item 详情。",
			detailFields: {
				runId: "Run ID",
				workflow: "Workflow",
				jobsCreated: "Jobs created",
				candidates: "Candidates",
			},
			itemsTableCaption: "Ingest run items",
			itemsTableHeaders: {
				videoUid: "Video UID",
				title: "Title",
				job: "Job",
				type: "Type",
				status: "Status",
			},
		},
		feedPage: {
			metadataTitle: "Digest Feed",
			metadataDescription:
				"SourceHarbor 的 digest feed，用于阅读条目、按 source/category/feedback 过滤，并从 feed curation 回到 reading pane、job trace 与 evidence。",
			kicker: "SourceHarbor Feed",
			heroTitle: "Digest Feed",
			heroSubtitle:
				"在一个阅读流里浏览 digest entries 和正文内容；需要时再加 source 与 category 过滤。",
			filterRegionLabel: "Digest filters",
			filterLabels: {
				source: "Source",
				category: "Category",
				feedback: "Feedback",
				sort: "Sort",
			},
			filterButton: "Filter",
			clearButton: "Clear",
			retryCurrentPageButton: "Retry current page",
			emptyTitle: "No AI digest entries yet",
			emptyFiltered: "没有条目匹配当前过滤条件。可以先清空过滤器再试。",
			emptyUnfiltered:
				"当前还没有处理完成的视频或文章。先添加订阅，再触发 intake。",
			goToSubscriptionsButton: "Go to subscriptions",
			paginationLabel: "Pagination",
			pagePrefix: "Page",
			previousPageButton: "← Previous page",
			nextPageButton: "Next page →",
			sourceOptions: {
				all: "All sources",
				youtube: "YouTube",
				bilibili: "Bilibili",
				rss: "RSS",
			},
			feedbackOptions: {
				all: "All feedback",
				saved: "Saved",
				useful: "Useful",
				noisy: "Noisy",
				dismissed: "Dismissed",
				archived: "Archived",
			},
			sortOptions: {
				recent: "Recent first",
				curated: "Curated first",
			},
			categoryOptions: {
				all: "All categories",
				tech: "Tech",
				creator: "Creator",
				macro: "Macro",
				ops: "Ops",
				misc: "Misc",
			},
			subscriptionFilterLabel: "Subscription",
		},
		subscriptionsPage: {
			metadataTitle: "Subscriptions",
			metadataDescription:
				"SourceHarbor 的 source intake 前门，突出 YouTube / Bilibili 强支持，同时接住 RSSHub 路由和通用 RSS feed，并用模板化引导来管理订阅。",
			kicker: "SourceHarbor Sources",
			heroTitle: "Subscriptions",
			heroSubtitle:
				"先从 YouTube 和 Bilibili 的强支持模板起步，再把宇宙扩到 RSSHub 路由和通用 feed，让 intake 从第一步就像产品前门，而不是内部字段编辑器。",
			supportMatrixTitle: "支持层级一眼看懂",
			supportMatrixDescription:
				"你可以把这里理解成 intake 菜单。某些来源已经是主打套餐，某些是通用入口，还有一些需要先经过路线级验证，不能一上来就吹成稳定能力。",
			supportLevels: {
				strong: {
					title: "强支持",
					description:
						"YouTube 频道和 Bilibili 创作者是当前最成形、最有引导感的订阅路径。",
				},
				general: {
					title: "通用支持",
					description:
						"RSSHub 路由和通用 RSS feed 可以扩展 source universe，但质量仍取决于具体 route 或 feed 本身。",
				},
				proving: {
					title: "待证明",
					description:
						"越偏门、越依赖 route 细节的来源形态，就越应该先当成真实实验，而不是默认稳定能力。",
				},
			},
			templateSectionTitle: "先选 source template",
			templateSectionDescription:
				"模板会先帮你锁定平台、source type 和 adapter 默认值，让这页更像引导式 intake，而不是生硬的内部编辑表单。",
			templateButton: "使用模板",
			templateSelectedButton: "当前模板",
			openMergedStoriesButton: "打开 merged stories",
			intakeGuideTitle: "当前 intake 契约",
			intakeGuideDescription:
				"这块会直白告诉你：当前模板最适合什么、应该先填哪一项，以及证明边界还在哪里。",
			guideLabels: {
				supportLevel: "支持层级",
				platform: "平台",
				sourceType: "来源类型",
				adapterType: "适配器",
				fillNow: "现在先填",
				proofBoundary: "证明边界",
			},
			templates: {
				youtubeChannel: {
					title: "YouTube 频道",
					description:
						"适合稳定的 YouTube intake。已知频道 ID、handle 或 landing URL 时，这条路最顺。",
					fillNow:
						"优先填频道 ID 或稳定频道 URL，再让 RSSHub route 跟它保持一致。",
					proofBoundary:
						"YouTube 本身是强支持，但如果你依赖 RSSHub intake，仍要看 route 是否长期稳定。",
				},
				bilibiliCreator: {
					title: "Bilibili 创作者",
					description:
						"适合已知 UID 的 Bilibili 创作者，目标是把 creator feed 做成可重复 intake。",
					fillNow: "先填创作者 UID 作为主标识，再补配套 RSSHub route。",
					proofBoundary:
						"Bilibili 创作者 intake 已经比较成形，但 route 断裂或上游变化仍需要盯住。",
				},
				rsshubRoute: {
					title: "RSSHub 路由",
					description:
						"适合更广的 source universe，只要 RSSHub 能把某条 route 规范成可用 feed，就能接进来。",
					fillNow:
						"先给一个可读的 source URL 或 handle，再把准确的 RSSHub route 填进去。",
					proofBoundary:
						"不能把“有 RSSHub”说成“所有 route 都稳”。每条 route 都应该用真实 runs 证明。",
				},
				genericRss: {
					title: "通用 RSS feed",
					description:
						"适合已经暴露干净 RSS 或 Atom feed 的来源，不需要平台专用捷径也能接入。",
					fillNow:
						"把精确 RSS 或 Atom feed URL 直接填进 Source value。除非你还想显式记录同一个 feed URL，否则可以把 Source URL 留空。",
					proofBoundary:
						"不同 feed 的质量差异很大。如果 feed 本身缺字段或很嘈杂，页面也应该保持诚实。",
				},
			},
			loadErrorTitle: "Unable to load subscriptions",
			retryCurrentPageButton: "Retry this page",
			editorTitle: "引导式 source editor",
			editorDescription:
				"当前模板会先把 intake 形状预填好，你只需要补充真正的 source 细节，而不是自己从零猜契约。",
			formLabels: {
				platform: "Platform",
				sourceType: "Source type",
				sourceValue: "Source value",
				adapterType: "Adapter type",
				sourceUrl: "Source URL (optional)",
				rsshubRoute: "RSSHub route (optional)",
				category: "Category",
				tags: "Tags (comma-separated, optional)",
				priority: "Priority (0-100)",
				enabled: "Enabled",
			},
			placeholders: {
				sourceValue: "Channel ID / UID / URL",
				sourceUrl: "https://example.com/feed.xml",
				rsshubRoute: "/youtube/channel/UCxxxx",
				tags: "ai,weekly,high-priority",
			},
			saveButton: "Save subscription",
			savePending: "Saving...",
			saveStatus: "Saving subscription settings",
			manualIntake: {
				title: "手动 source intake",
				description:
					"把 URL、handle、创作者空间页或 RSSHub route 直接贴进来。创作者级输入会落成订阅；YouTube/Bilibili 的直链视频会通过当前 one-off lane 进入 today。",
				placeholder:
					"https://space.bilibili.com/13416784\nhttps://www.youtube.com/@MindAmend\nhttps://www.youtube.com/watch?v=dQw4w9WgXcQ\n/36kr/newsflashes\nhttps://example.com/feed.xml",
				hint: "一行一个输入。Bilibili 空间页和 YouTube handle 会保存成订阅；直链视频会直接进今天；直链文章 URL 目前会诚实返回 unsupported。",
				categoryLabel: "新订阅默认分类",
				tagsLabel: "新订阅标签（逗号分隔，可选）",
				enabledLabel: "新建订阅后立即启用",
				submitButton: "运行手动 intake",
				submitPending: "正在 intake...",
				resultsTitle: "手动 intake 结果",
				resultsDescription:
					"每一行都会明确告诉你：这条输入最后是落成长期订阅、进入 today，还是因为当前运行时边界被拒绝。",
				summaryPrefix: "已处理",
				legend: {
					saveSubscription: "保存订阅",
					addToToday: "加入 today",
					unsupported: "当前不支持",
				},
				statusLabels: {
					created: "已创建",
					updated: "已更新",
					queued: "已排队",
					reused: "已复用",
					rejected: "已拒绝",
				},
				emptyState: "没有可落地目标",
			},
			currentTitle: "Current subscriptions",
			loadedPrefix: "Loaded",
			loadedSuffix: "subscriptions.",
			currentDescription: "可一次选择多行做批量分类更新。操作条会出现在底部。",
			platformOptions: {
				youtube: "YouTube",
				bilibili: "Bilibili",
				rss: "RSS / web source",
			},
			sourceTypeOptions: {
				url: "Source URL",
				youtubeChannelId: "YouTube channel ID",
				bilibiliUid: "Bilibili user UID",
				rsshubRoute: "RSSHub route",
			},
			adapterTypeOptions: {
				rsshubRoute: "RSSHub route",
				rssGeneric: "Generic RSS",
			},
			categoryOptions: {
				misc: "Other",
				tech: "Tech",
				creator: "Creator",
				macro: "Macro",
				ops: "Operations",
			},
		},
		searchPage: {
			metadataTitle: "Search",
			metadataDescription:
				"SourceHarbor 的 grounded search 与 Ask 入口，基于 digests、transcripts、outlines 与 knowledge cards 做 citation-first retrieval。",
			searchKicker: "SourceHarbor Search Front Door",
			askKicker: "SourceHarbor Ask Front Door",
			searchTitle: "Search",
			askTitle: "Ask your sources",
			searchSubtitle:
				"这是面向运营者的真实检索前台。它把 digest、transcript、outline 和 knowledge cards 变成可回跳、可审计的结果。",
			askSubtitle:
				"这是一个建立在 briefing 上下文之上的 Ask 前门。带上 watchlist 时，它可以先给当前答案、再给最近变化、最后给 citations；不带上下文时，就退回 raw grounded retrieval。",
			searchFormTitle: "Search your sources",
			askFormTitle: "Ask in grounded mode",
			searchFormDescription:
				"`keyword` 目前最稳。Search 已经覆盖视频强支持来源与 RSS 驱动的 source family，`semantic` 和 `hybrid` 仍保持 experimental 呈现。",
			askFormDescription:
				"先带上 watchlist 或 briefing 上下文，再把问题收敛成 cited retrieval，这样答案、变化和证据就能留在同一页。",
			queryLabel: "Query",
			questionLabel: "Question",
			queryPlaceholder: "agent workflow、retry policy、knowledge cards...",
			questionPlaceholder:
				"最近几轮到底怎么提 retry policy、agent workflow 或 knowledge cards？",
			searchHint: "每条结果都应该能回跳到 job trace、knowledge 或 source URL。",
			askHint:
				"如果你想拿到“答案 + 变化 + citations”，先挂上 watchlist briefing；不带上下文时，Ask 会诚实地退回 raw grounded retrieval。",
			askContextLabel: "Briefing 上下文",
			askContextTitle: "Ask 现在能站住脚的上下文",
			askContextDescription:
				"先选一个 watchlist，或者从 Briefings 打开 Ask，这页才能先复用真实 briefing，再去看问题级证据。",
			askContextEmptyOption: "还没有 briefing 上下文",
			askContextMissingTitle: "先补 briefing 上下文",
			askContextMissingDescription:
				"Ask 仍然可以搜原始证据，但如果没有 watchlist briefing，它就不能诚实地把页面组织成“答案 + 变化”视图。",
			askContextTopicLabel: "聚焦的 story / topic",
			askSelectionBasisLabel: "选择依据",
			askSelectionBasis: {
				requested_story_id: "指定 story",
				query_match: "问题匹配",
				suggested_story_id: "推荐 story",
				first_story: "首个可见 story",
				none: "尚未选定 story",
			},
			askOpenBriefingButton: "打开当前 briefing",
			askClearContextButton: "清除 briefing 上下文",
			askClearStoryContextButton: "清除 story 聚焦",
			modeLabel: "Mode",
			groundingModeLabel: "Grounding mode",
			platformLabel: "Platform",
			platformPlaceholder:
				"youtube、bilibili、rss、rsshub、github、newsletter ...",
			topKLabel: "Top K",
			searchButton: "Search",
			askButton: "Ask",
			clearButton: "Clear",
			platformOptions: {
				all: "All source families",
				youtube: "YouTube",
				bilibili: "Bilibili",
				rss: "RSS / web source",
			},
			modeOptions: {
				keyword: "Keyword",
				semantic: "Semantic (experimental)",
				hybrid: "Hybrid (experimental)",
			},
			searchTruthTitle: "Current truth",
			askTruthTitle: "Grounded Ask mode",
			searchTruthPrimary:
				"Search 是一个建立在真实 retrieval backend 之上的 production-facing front door，而它背后的 retrieval substrate 已经不止两家视频网站。",
			searchTruthSecondary:
				"默认 picker 仍然是刻意收窄的，但更宽的 source family 已经通过同一套后端 contract 和 query surface 往外延伸。",
			askTruthPrimary:
				"今天已经存在的是：基于 watchlist briefing 的答案 contract，以及 cited retrieval、job trace、knowledge cards 和原始来源链接。",
			askTruthSecondary:
				"还没有的是：一个脱离 briefing 上下文、也能到处成立的全局 free-form answer engine。",
			askTruthNote:
				"如果没有 watchlist 上下文，Ask 仍然会诚实地退回 grounded retrieval，而不是假装答案层已经无处不在。",
			askTruthContractLead:
				"Current contract: 先给答案，再给最近变化，最后给 citations，而且整条链都可回查。",
			searchTruthCta: "打开 Ask mode",
			askTruthCta: "打开 Ask details",
			openRawSearchButton: "Open raw search",
			askContractArtifactLabel: "Ask contract artifact",
			searchContractTitle: "Result contract",
			askContractTitle: "Best current use",
			searchContractPrimary:
				"每条命中都带 snippet、source type、score，以及跳转到 job trace、knowledge page 或原始来源 URL 的入口。",
			searchContractSecondary:
				"如果语料为空，Search 应该给出诚实的 empty state，而不是编一个答案。",
			askContractPrimary:
				"当你带着 watchlist briefing 来 Ask 时，这一页会把当前答案、最新变化和证据回跳放在同一页上。",
			askContractSecondary:
				"如果你没有挂 briefing，上面这套 answer view 就不会硬装存在，而会退回 raw grounded retrieval。",
			searchResultsTitle: "Results",
			askResultsTitle: "Grounded result set",
			askErrorTitle: "Ask failed",
			askErrorDescription:
				"retrieval layer 已存在，但这次问题没有返回有效结果。先重试，不要直接把它当成模式不可用。",
			askExpectationTitle: "What to expect",
			askExpectationDescription:
				"如果你想用自然语言提问，但又不想假装系统已经有 grounded answer model，就用这一页。每条结果都应该把你带回 job trace、knowledge cards 或原始来源。",
			askSummaryTitle: "Best evidence for your question",
			askSummaryQuestionPrefix: "Question",
			askSummaryHitsPrefix: "Evidence hits",
			askAnswerTitle: "当前最可信的答案",
			askAnswerGroundedState: "基于 briefing",
			askAnswerNeedsContextState: "需要上下文",
			askAnswerUnavailableState: "briefing 不可用",
			askAnswerNoConfidentState: "还不能自信回答",
			askAnswerGroundedDescription:
				"现在的 Ask 可以作为 briefing-aware 前门来回答：先给当前答案，再给最近变化，最后把证据摊开。",
			askAnswerContextOnlyDescription:
				"当前还没有具体问题，所以 Ask 先展示 briefing 里的当前答案，再等你继续缩小范围。",
			askAnswerUnavailableDescription:
				"watchlist 还在，但 briefing object 当前不可用，所以 Ask 还不能诚实地组出 answer layer。",
			askAnswerNoConfidentDescription:
				"当前 briefing 给了上下文，但这个问题还没有返回足够扎实的 grounded evidence，所以不能硬说答案已经成立。",
			askAnswerGroundedNote:
				"这个答案基于当前 watchlist briefing，并由下面的引用证据托底。",
			askAnswerContextOnlyNote:
				"这是当前 briefing 的答案。继续补问题或缩小问题，才能把它压到 question-level evidence。",
			askAnswerFallbackTitle: "当前 briefing 答案",
			askAnswerWhyLabel: "为什么这是当前答案",
			askStoryFocusTitle: "当前答案依赖的 story focus",
			askStoryFocusDescription:
				"你可以把它理解成 Ask 当前踩着哪条 story 在回答，然后再往 changes 和 evidence 往下钻。",
			askStorySwitcherTitle: "切换 story focus",
			askStorySwitcherDescription:
				"保留同一个问题，但把 answer layer 切到 briefing 里的另一条 story 上，方便比较不同 narrative。",
			askNoEvidenceTitle: "No cited evidence yet",
			askNoEvidenceDescription:
				"试着把问题收窄、切回 keyword mode，或者先处理更多 sources，再判断这是不是能力缺口。",
			askQuestionEvidenceTitle: "这个问题对应的证据",
			askQuestionEvidenceDescription:
				"这些命中来自当前 retrieval layer。你可以用它们验证上面的答案，或者推翻上面的答案。",
			askCitationsTitle: "支撑当前答案的 citations",
			askCitationsDescription:
				"这些入口会把你直接带回真正支撑答案的 story、card、compare 视图或原始来源。",
			askOpenCitationRouteButton: "打开 cited route",
			askFeaturedRunsDescription:
				"这些 runs 仍然是回看“当前答案背后最新收据”的最快入口。",
			askChangesFallbackDescription:
				"只有挂上 watchlist briefing，Ask 才能诚实地讲“最近变了什么”。",
			askFallbackActionsTitle: "下一步建议",
			searchResultsPrefix: "Showing cited retrieval results",
			askResultsPrefix: "Evidence candidates",
			searchRunPrompt: "先跑一个 query，再检查 grounded retrieval results。",
			askRunPrompt:
				"先跑一个 grounded question，再检查 grounded retrieval results。",
			requestFailed: "当前 retrieval 请求失败。先重试，再看 API health。",
			noResults:
				"当前还没有 grounded results。通常表示语料为空，或查询条件太窄。",
			askResultsAriaLabel: "Ask evidence results",
			groundedEvidenceTitle: "Grounded evidence",
			openJobTraceButton: "Open job trace",
			openKnowledgeCardsButton: "Open knowledge cards",
			openFeedEntryButton: "Open feed entry",
			openSourceButton: "Open source",
			knowledgeCardsSourceLabel: "Knowledge cards",
			experimentalMode: "experimental mode",
		},
		watchlistsPage: {
			metadataTitle: "Watchlists",
			metadataDescription:
				"保存 SourceHarbor watchlists，用于持续追踪 topic、claim kind、platform 与 source matcher，并把它们接到趋势与通知 readiness。",
			kicker: "SourceHarbor Compounders",
			heroTitle: "Watchlists",
			heroSubtitle:
				"把它理解成长期追踪清单。你不是只搜一次就走，而是把值得反复回看的主题、claims 或来源钉住。",
			saveTitle: "保存 watchlist",
			saveDescription:
				"当前支持 `topic_key`、`claim_kind`、`platform` 和 `source_match`。Wave 1 先做 persistent tracking，再把更深的 external alerts 接进来。",
			nameLabel: "名称",
			namePlaceholder:
				"重试策略、AI workflow、YouTube AI 频道、Claude Code 更新...",
			watchTypeLabel: "追踪类型",
			matcherValueLabel: "匹配值",
			matcherValuePlaceholder:
				"retry-policy、claim_kind、youtube、/channel-name、codex、claude-code ...",
			deliveryLabel: "投递方式",
			enabledLabel: "启用",
			saveButton: "保存 watchlist",
			updateButton: "更新 watchlist",
			createNewButton: "新建一个",
			openTrendViewButton: "打开 merged story 视图",
			openBriefingButton: "打开 briefing",
			alertTitle: "提醒 readiness",
			alertDescription:
				"SourceHarbor 现在已经能保存 watchlist 并在 dashboard 内复用。外发提醒是否 ready，要看 notification gate，而不是看表单有没有提交成功。",
			alertFallback:
				"当前拿不到 notification gate，先以 dashboard tracking 为主。",
			openNotificationSettingsButton: "打开通知设置",
			currentTitle: "当前 watchlists",
			currentDescription:
				"这些是已经持久化的 tracking objects。它们不是 UI 壳子，而是当前可保存、可读取、可挂趋势页的真实对象。",
			currentError: "当前无法读取 watchlists。先确认 API health，再重试这页。",
			currentEmpty:
				"还没有 watchlists。先保存一个主题或来源，这页才会开始像持续追踪面板，而不是空白表单。",
			updatedPrefix: "更新时间",
			enabledState: "启用中",
			pausedState: "已暂停",
			editButton: "编辑",
			viewTrendButton: "查看趋势",
			deleteButton: "删除",
			recentMovementTitle: "最近变化",
			recentMovementDescription:
				"先看最近 3 次变化，确认这个 watchlist 值不值得继续追。更完整的连续变化视图在 trend page。",
			openJobButton: "打开 Job",
			matchedCardsPrefix: "匹配卡片",
			addedTopicsPrefix: "新增主题",
			removedTopicsPrefix: "移除主题",
			noneValue: "无",
			matcherOptions: {
				topicKey: "Topic key",
				claimKind: "Claim kind",
				platform: "Platform",
				sourceMatch: "Source match",
			},
			deliveryOptions: {
				dashboard: "仅 Dashboard",
				email: "准备好后发邮件",
			},
		},
		trendsPage: {
			metadataTitle: "Trends",
			metadataDescription:
				"查看 SourceHarbor watchlists 的跨运行趋势与 merged story，把多个来源里反复出现的主题收拢成可见产品面，同时保留最近证据运行。",
			kicker: "SourceHarbor Trends",
			heroTitle: "Merged source stories",
			heroSubtitle:
				"这里开始把重复出现的 watchlist 命中收拢成可见 story，而不是只剩散装 diff。上面的 merged story 负责给你主线，下面的原始 runs 负责给你收据。",
			chooseTitle: "选择 watchlist",
			chooseDescription:
				"先选一个 watchlist，再看 source coverage、merged stories 和最近 evidence runs。页面会保持诚实，不假装已经有全自动大叙事层。",
			empty: "先保存至少一个 watchlist，这里才会出现真正可比的连续变化视图。",
			matcherLabel: "匹配器",
			recentRunsLabel: "最近运行数",
			matchedCardsLabel: "匹配卡片数",
			sourceCoverageTitle: "Source coverage",
			sourceCoverageDescription:
				"这里展示的是当前 watchlist 真正吃到的 source family，依据是实际匹配到的 runs 和 cards。",
			sourceCoverageRunsLabel: "运行数",
			sourceCoverageCardsLabel: "匹配卡片",
			mergedStoriesTitle: "Merged stories",
			mergedStoriesDescription:
				"下面每张卡会把同一个 topic 或 claim 在多次运行里的重复出现收拢起来，让“同一件事被多个来源反复提到”开始变成可见产品面。",
			mergedStoriesEmpty:
				"当前还没有足够重复的 topic 或 claim 形成 merged story。随着更多 runs 进入，这里会先长出来。",
			sourceCountLabel: "来源数",
			runCountLabel: "运行数",
			latestSeenLabel: "最近出现",
			recentEvidenceTitle: "最近 evidence runs",
			recentEvidenceDescription:
				"原始 run-by-run 变化仍然保留在下面，这样每个 merged story 都还能回到真实收据。",
			openBriefingButton: "打开 briefing",
			editWatchlistButton: "编辑 watchlist",
			openJobButton: "打开 Job",
			openKnowledgeButton: "打开 Knowledge",
			openSourceButton: "打开来源",
			addedTopicsPrefix: "新增主题",
			removedTopicsPrefix: "移除主题",
			addedClaimKindsPrefix: "新增 claim kinds",
			removedClaimKindsPrefix: "移除 claim kinds",
			noneValue: "无",
		},
		briefingsPage: {
			metadataTitle: "Briefings",
			metadataDescription:
				"SourceHarbor 的统一 watchlist briefing 入口，先讲当前主线，再讲最近变化，最后回到具体证据。",
			kicker: "SourceHarbor Briefings",
			heroTitle: "Unified briefings",
			heroSubtitle:
				"先看这件事现在在说什么，再看哪里变了，最后点进收据。它是建立在 watchlists、merged stories、jobs 和 knowledge 之上的最小真实 unified story 产品线。",
			truthTitle: "Truthful product line",
			truthDescription:
				"这页复用了真实 watchlists、merged stories 与 evidence links。它不是在宣称自己已经是全自动跨源融合引擎。",
			truthPrimary:
				"你可以把它理解成 briefing board：先看导语，再看变化，再看底下的原始材料。",
			truthSecondary:
				"它始终绑着 watchlists、jobs、knowledge cards 和原始来源，所以你可以随时回查收据。",
			openWatchlistsButton: "打开 watchlists",
			openTrendsButton: "打开 trends",
			chooseTitle: "选择 briefing",
			chooseDescription:
				"先选一个 watchlist，再加载对应的 briefing object。入口统一了，但底层 tracking object 仍然是明确可见的。",
			empty:
				"先保存至少一个 watchlist，这页才能加载真实 briefing，而不是空壳。",
			unavailableTitle: "Briefing 暂不可用",
			unavailableDescription:
				"选中的 watchlist 还在，但 briefing object 当前不可用。等 API route ready 或后端响应恢复后再重试。",
			overviewTitle: "这件事现在在说什么",
			overviewDescription:
				"先读这里。它是把多个来源当前反复在讲的同一件事收成一段 operator summary。",
			sourcesLabel: "来源数",
			runsLabel: "运行数",
			storiesLabel: "故事组",
			matchedCardsLabel: "匹配卡片",
			latestSeenLabel: "最近出现",
			generatedLabel: "生成时间",
			currentWatchlistLabel: "当前 watchlist",
			matcherLabel: "匹配器",
			primaryStoryLabel: "主线 story",
			signalsTitle: "当前信号",
			noSignals: "当前还没有被提炼出的重点信号。",
			openTrendButton: "打开 trend 视图",
			editWatchlistButton: "编辑 watchlist",
			askBriefingButton: "围绕这个 briefing 提问",
			differencesTitle: "最近有哪些变化",
			differencesDescription:
				"把它理解成 briefing memo 里的“增量更新”区。每一条都指向值得继续查的变化，而不是逼你自己手工 diff 每次 run。",
			differencesEmpty:
				"当前还没有被提炼出的重点变化。随着 briefing route 变完整，这里会先长出来。",
			addedTopicsLabel: "新增主题",
			removedTopicsLabel: "移除主题",
			addedClaimKindsLabel: "新增 claim kinds",
			removedClaimKindsLabel: "移除 claim kinds",
			newStoryKeysLabel: "新增 story keys",
			removedStoryKeysLabel: "移除 story keys",
			compareTitle: "Compare 摘要",
			noCompareExcerpt: "当前还没有 compare excerpt。",
			openCompareButton: "打开 compare",
			changeJobsLabel: "支撑这次变化的 Jobs",
			openJobButton: "打开 Job",
			noneValue: "无",
			evidenceTitle: "证据下钻",
			evidenceDescription:
				"每张 evidence card 都保留回到 Job Trace、Knowledge cards 和原始来源的路径，不会把 briefing 做成无法追溯的黑盒。",
			evidenceEmpty:
				"当前还没有挂上 evidence cards。summary 可能先存在，drill-down 后补齐。",
			storyEvidenceTitle: "Story 证据",
			featuredRunsTitle: "Featured runs",
			askStoryButton: "围绕这个 story 提问",
			openKnowledgeButton: "打开 Knowledge",
			openSourceButton: "打开来源",
			openBriefingButton: "打开 briefing",
			unknownStoryLabel: "未命名 story",
			untitledEvidenceLabel: "未命名证据",
			noExcerpt: "暂时没有可展示的摘录。",
			platformUnknown: "未知平台",
		},
		proofPage: {
			metadataTitle: "Proof",
			metadataDescription:
				"SourceHarbor 的 proof boundary，说明 product surface、local supervisor proof、long live-smoke lane 与 remote proof 的边界。",
			kicker: "SourceHarbor Proof",
			heroTitle: "Proof boundary",
			heroSubtitle:
				"把它理解成“哪些话现在能大胆说，哪些还要看额外证据”的总开关。代码、docs、local runtime 和 remote proof 不是同一层账本。",
			nextTruthfulJumpsTitle: "下一跳 truthful 入口",
			nextTruthfulJumpsDescription:
				"这些入口都是已经存在的真实 surface，不是额外包装。",
			openCommandCenterButton: "打开 command center",
			openOpsButton: "打开 Ops inbox",
			openMcpButton: "打开 MCP quickstart",
			openBuildersButton: "打开 builder guide",
			openStatusButton: "打开 project status",
			layers: {
				productSurfaceTitle: "Product surface",
				productSurfaceBody:
					"README、runtime-truth、project-status、Search、Ask、MCP 和 Ops 共同说明 SourceHarbor 是什么，以及每条 claim 具体落在哪层。",
				localSupervisorTitle: "Local supervisor proof",
				localSupervisorBody:
					"`bootstrap -> up -> status -> doctor` 可以证明 repo-managed local stack 真的起来了，而且路由取自 `resolved.env`，不是假设默认值。",
				longSmokeTitle: "Long live-smoke lane",
				longSmokeBody:
					"`./bin/smoke-full-stack --offline-fallback 0` 比基础 local proof 更严格，但仍可能卡在 provider-side 的 YouTube、Resend 或 Gemini gate。",
				remoteProofTitle: "Remote proof",
				remoteProofBody:
					"Release badges、GitHub settings 与 external distribution claims 仍需要 fresh remote verification。local success 不能替代那一层。",
			},
		},
		playgroundPage: {
			metadataTitle: "Playground",
			metadataDescription:
				"SourceHarbor 的只读 sample playground，用清楚标注的 demo corpus、example jobs、retrieval 结果与 bundle shape 帮你快速理解产品。",
			kicker: "SourceHarbor Playground",
			heroTitle: "Read-only sample playground",
			heroSubtitle:
				"这里展示的是 clearly labeled sample corpus，不是 live production results。它的作用是在不接完整环境前先让你感知产品价值。",
			boundaryDescription:
				"Sample boundary：这个 playground 是 read-only 且 sample-labeled，不要把它当成 current operator state、current `main` proof 或 remote proof。",
			openSearchButton: "打开真实 Search",
			openProofButton: "打开 proof ladder",
			sampleSourcesTitle: "Sample sources",
			exampleJobsTitle: "Example jobs",
			retrievalResultsTitle: "Example retrieval results",
			exampleWatchlistsTitle: "Example watchlists and trend",
			recentRunsLabel: "Recent runs",
			exampleBundleTitle: "Example bundle shape",
			exampleBundleDescription:
				"把它当成一个可分享内部 evidence bundle 的心智模型。它是 sample，不是 live export。",
		},
		jobsPage: {
			metadataTitle: "Job Trace",
			metadataDescription:
				"查看 SourceHarbor 的 Job Trace、运行对比、evidence bundle 与 long-lived knowledge cards，并回到底层 pipeline 证据。",
			kicker: "SourceHarbor Job Trace",
			heroTitle: "Job Trace",
			heroSubtitle:
				"输入 job ID 后，你可以在同一个 operator surface 内看完整 pipeline state、compare drift 与 evidence bundle。",
			findTitle: "Find a job",
			findDescription:
				"输入 job ID 查看 step trail 与 artifact links。你可以从首页 recent videos 或 digest feed 直接跳回来。",
			findDescriptionPrefix:
				"输入 job ID 查看 step trail 与 artifact links。你也可以直接从",
			homeLinkLabel: "首页 recent videos",
			findDescriptionConnector: "或",
			digestFeedLinkLabel: "digest feed",
			findDescriptionSuffix: "跳回来。",
			jobIdLabel: "Job ID *",
			jobIdPlaceholder: "9be4cbe7-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
			searchButton: "Search",
			compareTitle: "与上一轮对比",
			compareDescription:
				"把它理解成“这次和上次相比，结果改了多少”。如果没有上一条成功任务，这里会明确告诉你没有可比较对象。",
			knowledgeTitle: "Knowledge cards",
			knowledgeDescription:
				"把它理解成“从这次结果里提炼出的长期可复用卡片”。它们比原始 digest 更像可积累的知识对象。",
			lookupFailedTitle: "Lookup failed",
			retryCurrentPageButton: "Retry current page",
			currentStatusPrefix: "Current job status",
			pipelineStatusPrefix: "pipeline status",
			acrossStepsSuffix: "steps",
			jobOverviewTitle: "Job overview",
			overviewFields: {
				jobId: "Job ID",
				videoId: "Video ID",
				status: "Status",
				finalPipelineStatus: "Final pipeline status",
				createdAt: "Created at",
				updatedAt: "Updated at",
			},
			viewInDigestFeed: "View in digest feed",
			downloadEvidenceBundle: "Download evidence bundle",
			evidenceBundleNote:
				"Evidence bundles 用于内部复用与异步协作，不应被当成 public release proof。",
			stepSummaryTitle: "Step summary",
			stepSummaryEmpty: "No step records yet.",
			stepSummaryCaption: "Job step summary table",
			stepSummaryHeaders: {
				step: "Step",
				status: "Status",
				retries: "Retries",
				startedAt: "Started at",
				finishedAt: "Finished at",
			},
			compareFields: {
				previousJob: "Previous job",
				addedLines: "Added lines",
				removedLines: "Removed lines",
			},
			compareDiffEmpty: "No line-level diff preview was produced.",
			compareEmpty:
				"No previous successful job is available for comparison yet.",
			knowledgeEmpty: "No knowledge cards generated yet.",
			degradationsTitle: "Degradations",
			degradationsEmpty: "No degradations recorded.",
			unknownValue: "unknown",
			naValue: "n/a",
			artifactIndexTitle: "Artifact index",
			artifactsEmpty: "No artifacts yet.",
			opensInNewTabSuffix: "(opens in a new tab)",
		},
		useCasesPage: {
			kicker: "SourceHarbor Use Case",
			whyTitle: "Why this page exists",
			whyDescription:
				"这些 use-case 页面是 discoverability surface，不是 hosted 产品承诺。这里的每条 claim 都应该能回到 SourceHarbor 的真实能力。",
			nextStepsTitle: "Next truthful steps",
			nextStepsDescription:
				"通过这些链接，从 copy 直接跳到真实 product surface、proof 或 sample playground。",
			proofCta: "Open proof ladder",
			builderTitle: "Builder fit",
			builderDescription:
				"把这些页面理解成面对 Codex、Claude Code、MCP clients 与 source-first builder workflows 的 truthful fit guide。",
		},
		builderSurfaces: {
			title: "通过 Codex、Claude Code 和 MCP 客户端接入",
			subtitle:
				"把 SourceHarbor 当作 agent-facing control tower 使用：走 MCP、HTTP API、薄的 repo-local CLI 门面和共享 TypeScript client layer，而不是复制一套新的业务逻辑。",
			mcpCta: "打开 MCP quickstart",
			codexCta: "打开 Codex workflow",
			claudeCodeCta: "打开 Claude Code workflow",
			proofCta: "查看 proof ladder",
			researchCta: "打开 research pipeline",
			resourceTitle: "打开今天已经 ship 的 builder 门",
			resourceDescription:
				"如果你现在就想开始接入，这几扇门就是最短路径：builders 说明、starter packs，以及 CLI / TypeScript SDK 的包级入口。",
			buildersGuideCta: "打开 builders 指南",
			starterPacksCta: "打开 starter packs",
			cliPackageCta: "查看 CLI 包",
			sdkPackageCta: "查看 TypeScript SDK",
			highlightPills: [
				"MCP-native",
				"Codex-ready",
				"Claude Code-ready",
				"HTTP API",
				"Thin repo CLI",
				"Proof-first",
			],
			cards: {
				reuse: {
					title: "一套控制平面，四个真实入口",
					description:
						"Web、HTTP API、MCP，以及薄的 repo-local CLI 门面都指向同一套 jobs、artifacts、grounded search 与 operator truth。",
					bullets: [
						"Search + Ask",
						"MCP + API",
						"Thin repo CLI",
						"共享 TypeScript client",
					],
				},
				proof: {
					title: "先看证据，再谈气氛",
					description:
						"Proof、runtime truth 和 project status 会明确告诉你哪些已经真实存在，哪些仍受外部条件限制，哪些还只是刻意保留的 bet。",
					bullets: ["Proof boundary", "Runtime truth", "Project status"],
				},
				compounders: {
					title: "值得反复回来用",
					description:
						"Watchlists、trends、bundles 和 sample playground 让 SourceHarbor 更像可复用的 research product，而不是一次性 summarizer。",
					bullets: ["Watchlists", "Trends", "Bundles"],
				},
			},
		},
	},
} as const;

export type AppMessages = (typeof MESSAGES)["en"];

function mergeMessages<T extends Record<string, unknown>>(
	base: T,
	override: Record<string, unknown> | undefined,
): T {
	if (!override) {
		return base;
	}
	const output = { ...base } as Record<string, unknown>;
	for (const [key, value] of Object.entries(override)) {
		const baseValue = output[key];
		if (
			value &&
			typeof value === "object" &&
			!Array.isArray(value) &&
			baseValue &&
			typeof baseValue === "object" &&
			!Array.isArray(baseValue)
		) {
			output[key] = mergeMessages(
				baseValue as Record<string, unknown>,
				value as Record<string, unknown>,
			);
			continue;
		}
		output[key] = value;
	}
	return output as T;
}

export function getLocaleMessages(
	locale: SupportedLocale = DEFAULT_LOCALE,
): AppMessages {
	if (locale === "en") {
		return MESSAGES.en;
	}
	return mergeMessages(
		MESSAGES.en,
		MESSAGES[locale] as Record<string, unknown>,
	);
}

export function formatCountPattern(pattern: string, count: number): string {
	const [singular, plural] = pattern.split("|").map((part) => part.trim());
	const template = count === 1 ? singular : (plural ?? singular);
	return template.replace("{count}", String(count));
}
