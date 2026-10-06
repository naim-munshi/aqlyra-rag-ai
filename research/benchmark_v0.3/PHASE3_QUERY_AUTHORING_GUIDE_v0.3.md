# Phase 3 — Tier A Query Authoring Guide v0.3

## Purpose

Define the construction and review standard for the 240 controlled natural-
language questions.

## Metric-aware design

The Tier A benchmark contains three semantic groups:

1. answerable;
2. unanswerable;
3. conflict/uncertainty.

Primary retrieval metrics are computed on the **answerable, non-conflict**
subset.

Unanswerable and conflict queries are retained as separate diagnostic tracks.

This prevents undefined or non-comparable relevance structure from being
silently treated as ordinary retrieval failure.

## Query categories

Each of the 48 documents receives one question from each category:

1. lexical-anchor;
2. semantic-paraphrase;
3. entity+attribute;
4. multi-hop;
5. distractor-heavy.

## Lexical-anchor

Retain one or more distinctive terms from the evidence but do not copy the
source sentence.

## Semantic-paraphrase

Use materially different wording and syntax while preserving the underlying
information need.

Avoid accidental source-sentence copying.

## Entity+attribute

Ask about a specific entity together with one property such as:

- time;
- threshold;
- quantity;
- eligibility;
- sequence;
- operational condition.

## Multi-hop

The answer must require at least two separate retrieval units.

A query is not multi-hop merely because two sentences mention the same topic.

Gold evidence must contain at least two positive units.

## Distractor-heavy

Use plausible topic/lexical overlap with one or more non-gold units.

The distractor should be relevant enough to compete in retrieval but must not
support the requested answer.

## Unanswerable

An unanswerable query must be plausible and unsupported by the complete
eligible corpus.

It must not be impossible, nonsensical, or dependent on obscure outside
knowledge.

Unanswerable queries have no positive gold qrels.

## Conflict

A conflict query requires at least two evidence units that materially
contradict one another.

Each conflict requires:

- conflict_group_id;
- at least two conflicting positive qrels;
- explicit resolution_rule.

A contradiction must be real, not merely different wording.

## Lexical-overlap control

Each query receives a manual/reviewed lexical-overlap bucket:

- low;
- moderate;
- high.

The bucket describes overlap between canonical query wording and the relevant
evidence, not retrieval score.

This metadata is for stratified analysis and quality control.

## Leakage controls

Canonical questions must not expose:

- document IDs;
- unit IDs;
- filenames;
- condition names;
- coverage percentages;
- masking policies;
- gold-answer wording used as a giveaway.

## Review

Every question must be checked for:

1. clarity;
2. category correctness;
3. answerability;
4. evidence alignment;
5. distractor validity;
6. lexical-overlap classification;
7. leakage;
8. multi-hop validity;
9. conflict validity;
10. exact gold answer.

Generated text remains `draft` until manually reviewed.

Only reviewed questions may enter a frozen benchmark release.

## Freeze rule

Changing a frozen document or question creates a new benchmark version and
new content hashes.
