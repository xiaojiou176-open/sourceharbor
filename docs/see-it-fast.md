# See It Fast

If the README is the front door, this page is the shop window.

This page is for fast evaluation. It is not a hosted demo, cloud sandbox, or one-click trial.

The goal here is simple:

1. show what SourceHarbor feels like when you read it
2. show what the finished output actually looks like
3. let you decide whether it is worth a deeper evaluation

If you like what you see here, the next step is [run it locally](./start-here.md), not "open the live app."

<p>
  <img
    src="./assets/sourceharbor-studio-preview.svg"
    alt="SourceHarbor first-look preview showing one finished reading sample with proof nearby."
    width="100%"
  />
</p>

## The 20-Second Mental Model

SourceHarbor is not just a summarizer.

It is a full intake-to-reading loop:

- sources come in from YouTube, Bilibili, and RSS
- a job-backed pipeline processes each item into a readable surface
- operators read the result in a calm timeline flow
- agents reuse the same evidence through API and MCP

The source story is intentionally uneven on purpose:

- YouTube and Bilibili are the strongest supported intake templates today
- RSSHub and generic RSS are real substrate paths, but they remain more generalized than the strongest video-first flows

## The Three Surfaces That Matter First

### 1. Reader

This is the finished reading surface.

What you should picture:

- one finished reading surface
- one clear title worth opening
- source identity and proof nearby, not in front
- a calm desk instead of a dashboard

Why it matters:

- it proves the repo is trying to become a reading product, not just a processing pipeline

### 2. Timeline

This is the reading desk.

Representative current feed shape:

- title: `Bilibili history milestone: the earliest surviving AV2`
- source label: `Bilibili · archive reading`
- category label: `Misc`
- body path: finished reader note plus nearby proof

Why it matters:

- the output is meant to be read as one calm story, not just stored as pipeline exhaust

### 3. Proof

This is the evidence surface.

What you inspect here:

- `job_id`
- status and pipeline final status
- step summary
- retry count
- artifact references

Why it matters:

- when something fails, you can debug with receipts instead of guesswork

## What The Result Looks Like

SourceHarbor's reading artifact template already tells the story of the output shape:

```markdown
# <title>

> Source: [Original video](<source_url>)
> Platform: <platform> | Video ID: <video_uid> | Generated at: <generated_at>

## One-Minute Summary
<tldr>

## What This Covers
<summary>

## Key Takeaways
<highlights>
```

That is the key idea:

- not just transcript text
- not just one collapsed summary blob
- a reusable artifact with traceable structure

## The 60-Second Evaluation Path

If you want confidence without booting the full stack yet:

1. Read [README.md](../README.md) for the public story.
2. Read [proof.md](./proof.md) for the evidence ladder.
3. Read [start-here.md](./start-here.md) if you want the shortest truthful local run.
4. Read [samples/README.md](./samples/README.md) if you want the clearly labeled sample corpus path.
5. Read [architecture.md](./architecture.md) only after the front door and proof feel clear.

If you want a real local run after that, go to [start-here.md](./start-here.md).

## If You Are Here As A Builder

Do not start here by default. Start with the reader-first sample first, then open the builder lane on purpose:

- [docs/builders.md](./builders.md)
- [docs/public-distribution.md](./public-distribution.md)
- [starter-packs/README.md](../starter-packs/README.md)
- [docs/compat/openclaw.md](./compat/openclaw.md)

## Builder Off-Ramp

If you are here as a builder, leave this page early and use the builder surfaces on purpose:

- [docs/builders.md](./builders.md)
- [docs/public-distribution.md](./public-distribution.md)
- [starter-packs/README.md](../starter-packs/README.md)
