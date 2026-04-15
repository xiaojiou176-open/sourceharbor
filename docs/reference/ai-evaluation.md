# AI Evaluation

SourceHarbor keeps a small, reviewable evaluation surface in [`evals/`](../../evals/).

## Current Assets

- `evals/baseline.json`: the baseline contract and regression policy
- `evals/golden-set.sample.jsonl`: sample cases and expected signals
- `evals/README.md`: how to read the assets
- `evals/rubric.md`: what counts as passing vs regressing

## Why The Surface Is Small

This repository is source-first. The goal is to make the evaluation contract inspectable without pretending there is a giant benchmark program behind every commit.

That also means the evaluation surface stays behind the reader-first front door:

- `README.md` and the frontstage routes explain what the product is for
- `proof.md` and `project-status.md` explain what is currently proven
- `evals/` explains how regression expectations are checked once you are already inside the engineering lane
