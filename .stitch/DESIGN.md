# Design System: SourceHarbor

## 0. Wave 2 Governance

Wave 2 is not a cosmetic refresh. It is the rulebook for turning the current
repo truth into one reader-first product family.

- Primary system: **Notion**
  - Use it for structure, information calmness, soft borders, and paper-like
    reading comfort.
- Secondary influence: **WIRED**
  - Use it only for homepage and feed editorial ordering, kicker rhythm, and
    section hierarchy.
- Temperature layer: **Claude**
  - Use it only for warmth, margin-note tone, and quiet reader-facing
    atmosphere.

SourceHarbor should feel like:

- Notion for the bones
- WIRED for the story order
- Claude for the warmth

Route hierarchy is fixed:

- `/` must have one dominant first action.
- `/subscriptions` must split atlas/frontstage from advanced object workbench.
- `/feed` must behave like a curation desk with a preview, not a second reader.
- `/reader/[documentId]` is the canonical finished reading surface.

Wave 2 banned primary systems:

- Linear
- Vercel
- Raycast
- Stripe
- WIRED
- The Verge
- Mintlify

## 1. Product Lens

SourceHarbor is a reader-first editorial product, not a generic dashboard and not an operator console wearing a nicer coat. Every page should help a person move from source intake to finished reading with as little cognitive drag as possible.

The route contract is fixed:

- `/` is an orientation shell that routes builders, operators, and readers into the right first hop. It may summarize choices, but it must never feel like the user has to decode a control room before they can start. It should feel like a command center with calm route-map energy, not a metrics wall.
- `/subscriptions` is the tracked-universe atlas plus the intake workbench. The emotional job is "show me what world I am attaching this source to."
- `/feed` is the curation desk. The left rail is the list, the right rail is the reading pane, and the filter bar is a small steering wheel, not the main event.
- `/reader` is the finished frontstage. The body is the hero, the warning is a contract taped to the margin, and evidence belongs in a secondary rail or drawer.
- Manual intake result cards must always tell the truth about affiliation: matched universe, new universe, one-off injection, or rejected path. Never hide this behind optimistic copy.

## 2. Visual Theme & Atmosphere

The atmosphere should feel like an editorial control tower: calm, evidence-heavy, and highly legible. Think "well-lit magazine desk with operator-grade honesty" rather than "AI dashboard" or "analytics cockpit."

- Density: balanced 5/10. There is enough information to orient a power user, but breathing room remains visible.
- Variance: restrained asymmetric 4/10. Use split layouts and supporting rails, but do not make the interface feel artsy or unpredictable.
- Motion: fluid but quiet 4/10. Motion should confirm focus changes and route entry, never compete with the reading task.
- Surface model: frosted paper over a cool neutral canvas, with one action accent and one warning system.

## 3. Color Palette & Roles

Use the repo's existing token language as the source of truth. The single action accent is indigo. Rose is a narrative wash used to soften reader-facing hero surfaces, not a second CTA system.

- **Canvas Mist** (`#F0F2F8`) — primary page background; the room the cards sit in
- **Surface White** (`#FFFFFF`) — cards, rails, and primary content surfaces
- **Surface Hover** (`#F8F9FF`) — low-emphasis hover or secondary surfaces
- **Ink Slate** (`#0F172A`) — primary text and headings
- **Muted Steel** (`#64748B`) — supporting text and quiet metadata
- **Soft Border** (`#E2E8F0`) — panel and control outlines
- **Action Indigo** (`#6366F1`) — primary CTA fill, focus family, selected emphasis
- **Action Indigo Dark** (`#4F46E5`) — pressed/hovered primary CTA state
- **Action Indigo Wash** (`#EEF2FF`) — low-emphasis selection background or supporting accent
- **Warning Amber** (`#D97706`) — yellow-warning contract state
- **Warning Wash** (`#FFFBEB`) — amber warning surface background
- **Success Green** (`#16A34A`) — success-only confirmations and completion badges
- **Destructive Rose** (`#E11D48`) — destructive or failure-only surfaces
- **Reader Rose Wash** (`rose-50/60` in current UI) — allowed only as a supporting reader/frontstage atmosphere layer, never as a competing action color

Color rules:

- Use semantic tokens and CSS variables first. Do not hardcode raw colors in product components unless they are being defined as tokens.
- Primary CTA text must stay white on indigo.
- Warning and success states must never rely on color alone. Pair them with words like "Yellow warning", "Clear", "Created", or "Rejected".
- Do not introduce a second saturated accent just to make a panel feel more "designed."

## 4. Typography Rules

SourceHarbor already has a strong typographic split. Preserve it.

- **App Shell / Neutral Chrome:** `Geist Sans` may appear in framework-owned or neutral shell chrome
- **Display / Section Headings:** `Newsreader` via `editorialSerif`
  - Use for page titles, high-level hero lines, and important section titles
  - Tight tracking, controlled scale, never shouting
- **Body / Frontstage UI Copy:** `Public Sans` via `editorialSans`
  - Use for explanatory copy, filters, labels, helpers, and panel text
  - Keep long-form support copy between 65ch and 74ch when possible
- **Evidence / Raw Inputs / Codes:** `IBM Plex Mono` via `editorialMono`, with `Geist Mono` acceptable in shell-owned neutral chrome
  - Use for URLs, handles, line-based intake input, IDs, and dense machine-readable text

Typography rules:

- Kicker copy is uppercase, compact, and slightly letter-spaced.
- Hero/body relationships should feel like editorial hierarchy, not marketing bombast.
- Reader body content should remain readable in a narrow text column and never expand into edge-to-edge prose.
- Do not replace this stack with generic "Inter everywhere" or a flashy serif/sans experiment.

## 5. Layout Principles

- Unified shell width: preserve the current contained reading shell around `1140px` for multi-panel routes, and `max-w-6xl` / `max-w-7xl` style containment for reader pages.
- Base spacing rhythm: 24px major gaps, 16px secondary gaps, 8px label/support gaps.
- One screen, one main task:
  - `/subscriptions`: inspect tracked universes or act in the intake workbench
  - `/feed`: browse the queue or read the selected item
  - `/reader`: read the document body first
- Favor split grids like `1.3 / 0.9`, `1.5 / 0.7`, or similar supportive asymmetry over equal-width "everything matters the same" dashboards.
- Three-up equal cards are allowed only for orientation strips on `/` or small route summaries. They are banned as the primary reading surface.
- Supporting rails must feel like margin notes, not a second homepage living beside the main content.
- Cards may be nested only when the nesting clarifies hierarchy. Avoid stacking frosted surfaces just to add chrome.

## 6. Component Stylings

### Buttons

- Primary action buttons use the indigo action system and white text.
- `hero` is reserved for the single dominant CTA in a local section.
- `outline`, `surface`, and `ghost` variants are for secondary actions, route pivots, and quiet controls.
- Button hover should deepen or slightly brighten the indigo family, not add neon glow.
- Keep primary CTAs sparse. A hero zone gets at most one dominant filled action.

### Cards and Surfaces

- Default card radius should feel soft and paper-like, not enterprise-sharp.
- `folo-surface` is the preferred shared surface language: soft border, high-opacity white surface, blur, and a restrained downward shadow.
- Reader and subscriptions cards can use rose-tinted or muted supporting washes, but the text and CTA system still anchor back to neutral + indigo.
- Cards should communicate hierarchy by spacing and copy tone before they rely on decorative treatment.

### Inputs and Forms

- Labels always sit above controls.
- Intake textareas and other raw-input fields can use mono when they represent machine-like input.
- Helper text lives below the field and should explain proof boundaries or formatting expectations.
- Error messages must be announced with `role="alert"` or another live region.
- Do not rely on placeholder-only forms.

### Badges and State Chips

- Badges should carry semantic meaning:
  - relation
  - support tier
  - warning status
  - topic label
  - queue/result state
- Status chips must not communicate meaning by hue alone. Pair color with an explicit label.

### Source Identity Cards

- These are one of the signature components of the product.
- Always preserve:
  - thumbnail frame
  - avatar or avatar fallback
  - relation badge
  - title + subtitle
  - metadata chips
- If actions exist, they belong in the lower utility rail and should read like navigation, not like an ad banner.

### Warning, Empty, Loading, and Error States

- **Yellow warning** must look like a printed contract marker beside a finished story, not a catastrophic red error panel.
- **Empty states** explain what the user should do next in plain language and, when appropriate, offer one clear CTA.
- **Loading states** use skeleton lines shaped like the real layout. Do not use generic spinners as the primary loading language.
- **Error states** use destructive tinting, truthful copy, and a direct retry path. They should never look identical to warnings.

## 7. Interaction and Motion

Motion is support copy, not decoration.

- Use the existing motion token family in `globals.css` as the baseline.
- Preferred easing: soft standard curves and spring-soft emphasis, never abrupt linear motion.
- Route entry can use small staggered reveals on the first few panels, but do not animate everything.
- Favor `transform` and `opacity` only.
- Hover feedback should be subtle:
  - tiny elevation change
  - modest background shift
  - no jumpy scale transforms that break reading stability
- Respect `prefers-reduced-motion`.

## 8. Responsive Rules

- Below 768px, all multi-column reading and intake layouts collapse to one column.
- There must be no horizontal overflow on primary content routes.
- Page headers may wrap their toolbar actions beneath titles; that is acceptable and preferred to squeezed controls.
- Source identity cards can compact their media layout on small screens, but they must still preserve thumbnail/avatar/relation structure.
- Reader body retains a readable text width even on large displays and uses clean full-width stacking on smaller screens.
- Tap targets should remain at least 44px tall where practical.

## 9. Shadcn / Semantic Token Guardrails

If a component exists in the shadcn-style layer, compose from that layer before inventing bespoke markup.

- Prefer semantic tokens such as `bg-background`, `text-muted-foreground`, and `border-border`.
- Use `Button`, `Card`, `Badge`, `Input`, `Textarea`, `Select`, and `Checkbox` as the first resort for shared UI primitives.
- Keep `CardHeader`, `CardContent`, and related composition intact instead of dumping everything into a single div.
- Use `gap-*` instead of `space-*`.
- Avoid manual dark-mode overrides when the semantic token already solves the problem.
- Interactive elements should only look clickable when they truly are clickable. Do not decorate static cards like fake buttons.
- When future forms become more complex, preserve the current contract of label + helper + live error. Do not regress into unlabeled custom form grids.

## 10. Route-Specific Experience Laws

### `/`

- The homepage may summarize multiple lanes, but it should still feel like a clean entry map.
- It must present one dominant first action before any supporting routes.
- It is allowed to use small orientation cards and resource clusters only after the primary path is obvious.
- Builder and distribution routes are secondary surfaces and must not compete with the reading path on the first screen.
- It must not feel denser or louder than the product routes it points to.
- Preview/specimen or sample-proof language is allowed here only when it is explicitly labeled as preview/specimen and never confused with live proof.

### `/subscriptions`

- Start with the atlas: show who is already tracked.
- The first screen must show atlas + intake posture + manual intake.
- The intake workbench is secondary but still visible on the first screen.
- Template catalog, support matrix, editor, and current subscription ledger belong to an advanced object-workbench layer, not the primary frontstage.
- Manual intake results must clearly show whether an item matched, created, reused, queued, or was rejected.
- Deep links to tracked universe, reader, and job trace belong in the result card utility rail.

### `/feed`

- The filter bar should stay compact and mechanically trustworthy.
- The selected tracked universe card is a context rail, not the main headline.
- The left list and right reading pane must feel like a single editorial workflow.
- The reading pane is a preview bridge, not the canonical finished article.
- `Open reader edition` is the primary bridge out of the preview; job and object links must stay secondary.
- Empty-feed states should route users back to subscriptions, not leave them in a dead end.

### `/reader`

- The document body is the frontstage.
- Margin notes, section outline, warnings, and evidence are supporting rails.
- Warning and coverage surfaces must feel honest, calm, and readable.
- Traceability and repair belong beside coverage as supportive proof rails, not as a control-panel takeover.
- Do not let operator verbs or debug language overpower the reading experience.

## 11. Banned Patterns

- No dashboard-first language on reader-facing routes
- No fake AI metrics, made-up percentages, or ornamental counters
- No emoji icons
- No neon glows, purple-on-white gimmicks, or second accent-color systems
- No hardcoded color literals in product components when a token exists
- No placeholder-only inputs
- No color-only warnings or status states
- No giant hero sections that bury the first useful action
- No "everything is a card" nesting that creates a second front page
- No burying tracked-universe affiliation behind vague success copy
- No reader pages that look like operator tooling
- No equal-width feature-grid clichés as the main content surface
- No homepage where builder, operator, and reader routes all look equally primary
- No feed preview that visually competes with reader detail
- No preview/specimen route that visually impersonates live proof

## 12. Definition Of Done For Future UI Work

A new SourceHarbor surface is only visually complete when:

- the page has one obvious first action
- source identity and provenance honesty are visible where they matter
- warning, empty, loading, success, and error states all have explicit copy and structure
- semantic tokens are used instead of bespoke color hacks
- mobile collapse preserves hierarchy instead of merely shrinking it
- the result still feels like one product family with `/subscriptions`, `/feed`, and `/reader`
