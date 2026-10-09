# Tier-A v0.3.3 Human Review Instructions v0.1

## Status

This is a human-review instrument for the machine-generated
120-query review sample.

The benchmark source files remain unchanged.

Do not change `queries.csv`, `documents.csv`, or `qrels.csv`
during review.

## Review decision

Use:

- `PASS` — annotation is supported by the supplied source text.
- `REVISE` — annotation has a correct underlying intent but requires a concrete correction.
- `REJECT` — query/evidence construction is materially invalid for evaluation.

## Review checks

For every query, independently inspect:

### 1. Question validity

Confirm that the question is grammatical, understandable,
specific enough to evaluate, and does not contain accidental
template artifacts.

### 2. Gold answer

For answerable queries:

- the gold answer must be supported by the gold evidence;
- it must answer the question directly;
- it must not introduce unsupported facts.

For unanswerable queries:

- the supplied corpus units must not contain sufficient evidence
  to establish the requested answer.

For conflict queries:

- the evidence must contain the intended conflicting information;
- the resolution rule must be understandable.

### 3. Gold evidence

For every gold evidence unit:

- the unit must materially support the answer or conflict;
- the highlighted evidence span must occur in the supplied text;
- no essential evidence unit should be missing.

### 4. Multi-hop

When `requires_multi_hop=true`, at least two distinct evidence
units must be necessary to derive the intended answer.

A query should not be labeled multi-hop merely because two units
happen to contain related information.

### 5. Conflict

For `answerability=conflict`:

- the qrels should identify the conflicting units;
- the units should actually present incompatible claims or values
  relevant to the question;
- the conflict-group metadata should be consistent.

### 6. Distractors

Distractor units must be legitimate corpus units and must not
already be gold evidence.

Check that distractors are plausibly confusing but do not
accidentally contain the intended answer.

## Reviewer fields

`reviewer_decision`
`gold_answer_ok`
`gold_evidence_ok`
`qrels_ok`
`answerability_ok`
`multi_hop_ok`
`conflict_ok`
`distractor_ok`
`reviewer_notes`

Use `yes/no` for the boolean fields.

Leave no reviewer field blank after reviewing a query.

## Important

A completed automated audit is not equivalent to human review.

The benchmark must not be described as human-frozen until the
selected queries have actually been reviewed and accepted.
